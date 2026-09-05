"""End-to-end check of the import -> register -> verify merge.

A student who already holds a scholarship says so on the registration form, in
the Scholarship Data card, and uploads the proof there. The SDSO decides it on
the account verification queue, in the same action that releases the account:
there is no separate Link Scholarship page for the student and no separate Link
Requests queue for the office.

Runs against a throwaway test database, so db.sqlite3 is never touched.
"""
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile

from api.models import (
    User, StudentProfile, Scholarship, Application, ImportedScholar,
    ScholarshipLinkRequest, SystemSettings, Notification,
)


def archive_rows(response, kind=None):
    """The rows the archive table rendered, optionally of one record shape.

    'imported' rows come from an office spreadsheet, 'award' rows from an
    Application. The merge these tests cover is exactly the moment a scholar
    stops being the first and becomes the second.
    """
    rows = [row for group in response.context['scholar_groups'] for row in group['rows']]
    return [row for row in rows if kind is None or row['kind'] == kind]


def a_proof(name='award.pdf', size=1024):
    return SimpleUploadedFile(name, b'x' * size, content_type='application/pdf')


REGISTRATION = {
    'account_type': 'student',
    'first_name': 'Juan',
    'last_name': 'Dela Cruz',
    'email': 'juan@bipsu.edu.ph',
    'student_id': '2022-0001',
    'password': 'sekritpw123',
    'confirm_password': 'sekritpw123',
    'year_level': '1',
}


class RegisterWithAScholarshipTest(TestCase):
    """The whole path: the office imports, the student registers, the SDSO verifies."""

    def setUp(self):
        s = SystemSettings.objects.create(pk=1, academic_year='26-1',
                                          active_semester='1st Semester')
        self.label = s.academic_year
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[],
        )
        # 1. VPSEA imports the scholar from the office's Excel file.
        self.archive = ImportedScholar.objects.create(
            scholarship_type='Academic', term_label=self.label,
            last_name='Dela Cruz', first_name='Juan', middle_name='S',
            course='BSCS', year_level=3, gwa=1.25, student_id='2022-0001',
            barangay='Poblacion', municipality='Naval', province='Biliran',
            award_number='AW-99', imported_from='Academic_26-1.xlsx',
        )
        self.vpsea = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph', password='pw',
            role='vpsea',
        )

    def _register(self, **extra):
        data = dict(REGISTRATION, **{
            'has_scholarship': 'on',
            'scholarship_type': 'Academic',
            'award_number': 'AW-99',
            'notes': 'Award letter attached',
            'proof_document': a_proof(),
        })
        data.update(extra)
        return Client().post('/register/', data)

    def _office(self):
        c = Client()
        self.assertTrue(c.login(email='vpsea@bipsu.edu.ph', password='pw'))
        return c

    # ── Registering ─────────────────────────────────────────────────────────

    def test_the_declaration_is_stored_with_the_registration(self):
        r = self._register()
        self.assertEqual(r.status_code, 302)

        req = ScholarshipLinkRequest.objects.get()
        self.assertEqual(req.status, 'Pending')
        self.assertEqual(req.scholarship_type, 'Academic')
        self.assertEqual(req.award_number, 'AW-99')
        self.assertEqual(req.term_label, self.label)
        self.assertEqual(req.student.student_id, '2022-0001')
        # The account itself is still waiting; declaring a scholarship does not
        # let anybody past the SDSO.
        self.assertTrue(req.student.user.awaiting_verification)

    def test_registering_without_one_stores_nothing(self):
        r = Client().post('/register/', dict(REGISTRATION))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)

    def test_a_declaration_with_no_scholarship_named_is_refused(self):
        r = self._register(scholarship_type='')
        self.assertContains(r, 'Say which scholarship you already hold')
        self.assertEqual(User.objects.filter(email=REGISTRATION['email']).count(), 0)

    def test_the_proof_is_validated_server_side(self):
        r = self._register(proof_document=a_proof('virus.exe'))
        self.assertContains(r, 'Unsupported file type')

        r = self._register(proof_document=a_proof(size=6 * 1024 * 1024))
        self.assertContains(r, 'too large')

        data = dict(REGISTRATION, has_scholarship='on', scholarship_type='Academic')
        r = Client().post('/register/', data)
        self.assertContains(r, 'Proof document is required.')

        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)
        self.assertEqual(StudentProfile.objects.count(), 0)

    # ── Verifying ───────────────────────────────────────────────────────────

    def test_the_queue_offers_the_imported_row_as_a_match(self):
        self._register()
        r = self._office().get('/vpsea/accounts/')
        self.assertEqual(r.status_code, 200)

        account = r.context['pending'][0]
        self.assertEqual(account.declared.scholarship_type, 'Academic')
        self.assertEqual([x.id for x in account.archive_candidates], [self.archive.id])
        self.assertContains(r, 'Scholarship declared at registration')

    def test_verifying_the_account_merges_without_duplicating(self):
        self._register()
        req = ScholarshipLinkRequest.objects.get()
        profile = req.student
        office = self._office()

        # Archives before the decision: the imported row, and no live scholar.
        r = office.get('/vpsea/archives/?type=Academic')
        self.assertEqual(r.context['total'], 1)
        self.assertEqual(len(archive_rows(r, 'imported')), 1)
        self.assertEqual(len(archive_rows(r, 'award')), 0)

        r = office.post('/vpsea/accounts/', {
            'user_id': profile.user_id, 'action': 'approve',
            'archive_id': self.archive.id, 'message': 'Verified vs COR',
        })
        self.assertEqual(r.status_code, 302)

        req.refresh_from_db()
        self.archive.refresh_from_db()
        profile.refresh_from_db()

        self.assertEqual(req.status, 'Approved')
        self.assertEqual(req.reviewed_by, self.vpsea)
        self.assertIsNotNone(req.reviewed_at)
        self.assertEqual(req.matched_archive_id, self.archive.id)
        self.assertEqual(self.archive.claimed_by_id, profile.id)

        # The declaration became a real Approved Application for this semester.
        app = Application.objects.get()
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.student_id, profile.id)
        self.assertEqual(app.source, 'link')
        self.assertEqual(app.school_year, '2026-2027')
        self.assertEqual(app.semester, '1st Semester')
        self.assertEqual(app.term_label, '26-1')
        self.assertEqual(req.linked_application_id, app.id)

        # Blank profile fields were backfilled from the office's import.
        self.assertEqual(profile.year_level, 3)
        self.assertEqual(profile.gwa, 1.25)
        self.assertEqual(profile.municipality, 'Naval')

        # The archives now show ONE entry, not two.
        r = office.get('/vpsea/archives/?type=Academic')
        self.assertEqual(r.context['total'], 1)
        self.assertEqual(len(archive_rows(r, 'imported')), 0)
        self.assertEqual(len(archive_rows(r, 'award')), 1)

        # And the account itself was released, with the student notified.
        profile.user.refresh_from_db()
        self.assertTrue(profile.user.can_sign_in)
        self.assertTrue(Notification.objects.filter(
            student=profile, title__contains='linked to your account').exists())

    def test_verifying_without_an_imported_row_still_records_the_award(self):
        self._register()
        req = ScholarshipLinkRequest.objects.get()
        self._office().post('/vpsea/accounts/', {
            'user_id': req.student.user_id, 'action': 'approve',
            'archive_id': '', 'message': '',
        })
        req.refresh_from_db()
        self.assertEqual(req.status, 'Approved')
        self.assertIsNone(req.matched_archive_id)
        self.archive.refresh_from_db()
        self.assertIsNone(self.archive.claimed_by_id)
        self.assertEqual(Application.objects.get().status, 'Approved')

    def test_a_past_semester_row_cannot_be_claimed(self):
        """History is never rewritten by this term's decision."""
        old = ImportedScholar.objects.create(
            scholarship_type='Academic', term_label='25-2',
            last_name='Dela Cruz', first_name='Juan', student_id='2022-0001',
        )
        self._register()
        req = ScholarshipLinkRequest.objects.get()
        office = self._office()

        account = office.get('/vpsea/accounts/').context['pending'][0]
        self.assertEqual([x.id for x in account.archive_candidates], [self.archive.id])
        self.assertEqual([x.id for x in account.other_semester_rows], [old.id])

        r = office.post('/vpsea/accounts/', {
            'user_id': req.student.user_id, 'action': 'approve',
            'archive_id': old.id, 'message': 'x',
        })
        self.assertIn('no+longer+available', r['Location'])
        old.refresh_from_db()
        self.assertIsNone(old.claimed_by_id)
        self.assertEqual(ScholarshipLinkRequest.objects.get().status, 'Pending')

    def test_rejecting_the_account_rejects_the_declaration_with_it(self):
        self._register()
        req = ScholarshipLinkRequest.objects.get()
        self._office().post('/vpsea/accounts/', {
            'user_id': req.student.user_id, 'action': 'reject',
            'message': 'Proof is unreadable',
        })
        req.refresh_from_db()
        self.assertEqual(req.status, 'Rejected')
        self.assertEqual(req.remarks, 'Proof is unreadable')
        self.assertEqual(Application.objects.count(), 0)
        self.assertTrue(Notification.objects.filter(
            student=req.student, title__contains='could not be verified').exists())

    def test_a_missing_programme_is_reported_rather_than_half_recorded(self):
        Scholarship.objects.all().delete()
        self._register()
        req = ScholarshipLinkRequest.objects.get()
        r = self._office().post('/vpsea/accounts/', {
            'user_id': req.student.user_id, 'action': 'approve', 'message': '',
        })
        self.assertIn('error=', r['Location'])
        req.refresh_from_db()
        self.assertEqual(req.status, 'Pending')
        # Neither half happened: no award, and the account is still waiting.
        self.assertEqual(Application.objects.count(), 0)
        self.assertTrue(req.student.user.awaiting_verification)

    def test_staff_type_is_a_single_canonical_key(self):
        from api.models import SCHOLARSHIP_TYPE_CHOICES
        keys = [k for k, _ in SCHOLARSHIP_TYPE_CHOICES]
        self.assertIn('Staff', keys)
        self.assertNotIn('NSU Staff', keys)

        Scholarship.objects.create(
            name='BiPSU Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
        )
        # The old 'NSU Staff' value is rejected; the canonical 'Staff' is taken.
        r = self._register(scholarship_type='NSU Staff')
        self.assertContains(r, 'Say which scholarship you already hold')

        self.assertEqual(self._register(scholarship_type='Staff').status_code, 302)
        req = ScholarshipLinkRequest.objects.get()
        self.assertEqual(req.scholarship_type, 'Staff')
        self.assertEqual(req.get_scholarship_type_display(), 'BiPSU Staff Scholarship')

        self._office().post('/vpsea/accounts/', {
            'user_id': req.student.user_id, 'action': 'approve', 'message': 'ok',
        })
        req.refresh_from_db()
        self.assertEqual(req.status, 'Approved')
        self.assertEqual(req.linked_application.scholarship.type, 'Staff')


class ChedTierDeclarationTest(TestCase):
    """A CHED scholar declaring their award has to say which tier it is.

    CHED grants Full Merit and Half Merit under one programme, and every
    masterlist reports the two in separate blocks — so without the tier the
    office cannot tell which block a linked scholar belongs in.
    """
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        # Deliberately named without 'Full' or 'Half': the programme name is
        # exactly what cannot be used to tell the two tiers apart.
        Scholarship.objects.create(
            name='CHED Merit', type='CHED', category='recommendation',
            description='x', eligibility='x', requirements=[],
        )
        User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph', password='pw',
            role='vpsea',
        )

    def _register(self, **extra):
        data = dict(REGISTRATION, **{
            'first_name': 'Ana', 'last_name': 'Reyes',
            'email': 'ana@bipsu.edu.ph', 'student_id': '2022-0002',
            'has_scholarship': 'on', 'scholarship_type': 'CHED',
            'award_number': 'CHED-01', 'notes': '',
            'proof_document': a_proof(size=512),
        })
        data.update(extra)
        return Client().post('/register/', data)

    def _office(self):
        c = Client()
        self.assertTrue(c.login(email='vpsea@bipsu.edu.ph', password='pw'))
        return c

    def test_a_ched_declaration_without_a_tier_is_refused(self):
        r = self._register()
        self.assertContains(r, 'Full Merit / Full Scholar')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)

    def test_the_tier_survives_verification_and_lands_in_the_full_block(self):
        from api.models import split_ched

        self.assertEqual(self._register(award_tier='Full').status_code, 302)
        req = ScholarshipLinkRequest.objects.get()
        self.assertEqual(req.award_tier, 'Full')

        self._office().post('/vpsea/accounts/', {
            'user_id': req.student.user_id, 'action': 'approve',
            'archive_id': '', 'message': '', 'award_tier': 'Full',
        })
        app = Application.objects.get(student=req.student)
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.form_data['scholar_type'], 'Full Merit / Full Scholar')

        full, half = split_ched([app])
        self.assertEqual((len(full), len(half)), (1, 0))

    def test_the_officer_can_correct_the_tier_the_student_chose(self):
        from api.models import split_ched

        self._register(award_tier='Full')
        req = ScholarshipLinkRequest.objects.get()
        office = self._office()

        # The queue offers the correction: a tier select preset to the
        # student's answer, beside the Verify button.
        page = office.get('/vpsea/accounts/')
        self.assertContains(page, 'name="award_tier"')
        self.assertContains(page, 'value="Half"')
        self.assertContains(page, 'The student declared')

        office.post('/vpsea/accounts/', {
            'user_id': req.student.user_id, 'action': 'approve',
            'archive_id': '', 'message': '', 'award_tier': 'Half',
        })
        req.refresh_from_db()
        self.assertEqual(req.award_tier, 'Half')

        app = Application.objects.get(student=req.student)
        self.assertEqual(app.form_data['scholar_type'], 'Half Merit / Partial Scholar')
        full, half = split_ched([app])
        self.assertEqual((len(full), len(half)), (0, 1))

    def test_other_programmes_do_not_carry_a_tier(self):
        Scholarship.objects.create(
            name='DOST Merit Scholarship', type='DOST', category='recommendation',
            description='x', eligibility='x', requirements=[],
        )
        # A tier posted for a non-CHED programme is ignored rather than stored.
        self.assertEqual(
            self._register(scholarship_type='DOST', award_tier='Full').status_code, 302)
        self.assertEqual(ScholarshipLinkRequest.objects.get().award_tier, '')


class ScholarshipDataCardTest(TestCase):
    """What the student can see of their own scholarship afterwards.

    The Link Scholarship page is gone, so the record of what they hold — and of
    a declaration still being checked — lives on My Profile, in a read-only
    Scholarship Data card. A student holding nothing sees no card at all.
    """
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        user = User.objects.create_user(
            username='noel@bipsu.edu.ph', email='noel@bipsu.edu.ph', password='pw',
            first_name='Noel', last_name='Cruz', role='student')
        self.profile = StudentProfile.objects.create(
            user=user, student_id='2022-0003', course='BSIT', year_level=2)
        self.c = Client()
        self.assertTrue(self.c.login(email='noel@bipsu.edu.ph', password='pw'))

    def test_no_card_while_the_student_holds_nothing(self):
        r = self.c.get('/student/profile/')
        self.assertEqual(r.context['scholarships_held'], [])
        self.assertNotContains(r, 'Scholarship Data')

    def test_an_award_is_named_on_the_card(self):
        Application.objects.create(
            student=self.profile, scholarship=self.scholarship, status='Approved',
            school_year='2026-2027', semester='1st Semester',
            award_number='AW-12', form_data={})
        r = self.c.get('/student/profile/')
        self.assertContains(r, 'Scholarship Data')
        self.assertContains(r, 'Academic Scholarship')
        self.assertContains(r, 'AW-12')

    def test_an_undecided_declaration_says_it_is_still_being_checked(self):
        ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='DOST', term_label='26-1')
        r = self.c.get('/student/profile/')
        self.assertContains(r, 'DOST Scholarship')
        self.assertContains(r, 'still verifying')

    def test_a_rejected_declaration_keeps_its_reason(self):
        ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='DOST', status='Rejected',
            remarks='The award number is not on the DOST list for this term.',
            term_label='26-1')
        r = self.c.get('/student/profile/')
        self.assertContains(r, 'not on the DOST list')

    def test_an_approved_declaration_is_shown_once_not_twice(self):
        """Approving one writes the award; listing both would double it."""
        app = Application.objects.create(
            student=self.profile, scholarship=self.scholarship, status='Approved',
            school_year='2026-2027', semester='1st Semester', form_data={})
        ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='Academic', status='Approved',
            term_label='26-1', linked_application=app)
        r = self.c.get('/student/profile/')
        self.assertEqual(len(r.context['scholarships_held']), 1)
