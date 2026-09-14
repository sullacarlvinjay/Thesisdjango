from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    ActivityLog, Application, ImportedScholar, Notification, Scholarship,
    ScholarshipLinkRequest, StudentProfile, SystemSettings, User,
)
from api.student_views import held_scholarship_types

PROFILE = '/student/profile/'
QUEUE = '/vpsea/accounts/'


def a_proof(name='award.pdf', size=1024):
    return SimpleUploadedFile(name, b'x' * size, content_type='application/pdf')


class AddScholarshipFromMyProfileTest(TestCase):
    def setUp(self):
        settings_obj = SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.label = settings_obj.academic_year

        for name, stype in (('DOST Scholarship', 'DOST'),
                            ('CHED Scholarship', 'CHED')):
            Scholarship.objects.create(
                name=name, type=stype, category='application',
                description='x', eligibility='x', requirements=[],
            )

        self.user = User.objects.create_user(
            username='juan@bipsu.edu.ph', email='juan@bipsu.edu.ph',
            password='sekritpw123', role='student',
            first_name='Juan', last_name='Dela Cruz',
            verification_status='approved', email_verified=True,
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2022-0001', course='BSCS', year_level=2)

        self.officer = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea',
        )

    def student(self):
        c = Client()
        self.assertTrue(c.login(email='juan@bipsu.edu.ph', password='sekritpw123'))
        return c

    def office(self):
        c = Client()
        self.assertTrue(c.login(email='vpsea@bipsu.edu.ph', password='pw'))
        return c

    def add(self, client=None, **extra):
        data = {
            'has_scholarship': 'on',
            'scholarship_type': 'DOST',
            'award_number': '2026-DOST-00194',
            'notes': 'Won it this term.',
            'proof_document': a_proof(),
        }
        data.update(extra)
        return (client or self.student()).post(PROFILE, data)

    def test_my_profile_carries_the_card(self):
        r = self.student().get(PROFILE)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['scholarship_blocked_reason'], '')
        self.assertIn('DOST', dict(r.context['scholarship_types']))
        self.assertContains(r, 'Scholarship Data')
        self.assertContains(r, 'I hold a scholarship the office has not recorded yet')

    def test_it_is_the_registration_forms_three_cards(self):
        r = self.student().get(PROFILE)
        slots = r.context['declaration_slots']
        self.assertEqual([s['n'] for s in slots], [1, 2, 3])
        self.assertEqual([s['suffix'] for s in slots], ['', '_2', '_3'])
        self.assertFalse(slots[0]['extra'])
        self.assertTrue(slots[1]['extra'])
        self.assertFalse(any(s['open'] for s in slots))
        self.assertContains(r, '+ I hold another scholarship')

    def test_saving_the_profile_files_it_for_the_active_term(self):
        r = self.add()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['saved'])
        self.assertEqual(r.context['declared_count'], 1)

        req = ScholarshipLinkRequest.objects.get()
        self.assertEqual(req.student, self.profile)
        self.assertEqual(req.scholarship_type, 'DOST')
        self.assertEqual(req.award_number, '2026-DOST-00194')
        self.assertEqual(req.status, 'Pending')
        self.assertEqual(req.term_label, self.label)
        self.assertTrue(req.filed_in_portal)

    def test_saving_the_profile_without_ticking_the_box_files_nothing(self):
        r = self.student().post(PROFILE, {'suffix': 'Jr.'})
        self.assertTrue(r.context['saved'])
        self.assertEqual(r.context['declared_count'], 0)
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)

    def test_two_scholarships_can_be_added_at_once(self):
        self.add(**{
            'has_scholarship_2': 'on',
            'scholarship_type_2': 'CHED',
            'award_tier_2': 'Full',
            'proof_document_2': a_proof('ched.pdf'),
        })
        self.assertEqual(
            sorted(ScholarshipLinkRequest.objects.values_list(
                'scholarship_type', flat=True)),
            ['CHED', 'DOST'])

    def test_the_same_programme_twice_is_refused(self):
        r = self.add(**{
            'has_scholarship_2': 'on',
            'scholarship_type_2': 'DOST',
            'proof_document_2': a_proof('again.pdf'),
        })
        self.assertContains(r, 'twice')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)

    def test_the_office_is_told_it_arrived(self):
        self.add()
        self.assertTrue(ActivityLog.objects.filter(
            action__contains='added a scholarship: DOST S&T Undergraduate '
                             'Scholarship').exists())

    def test_what_they_hold_is_listed_above_the_question(self):
        self.add()
        r = self.student().get(PROFILE)
        held = r.context['scholarships_held']
        self.assertEqual([h['type'] for h in held], ['DOST'])
        self.assertEqual(held[0]['status'], 'Pending')

    def test_it_waits_in_its_own_section_of_account_verification(self):
        self.add()
        r = self.office().get(QUEUE)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([req.pk for req in r.context['added_scholarships']],
                         [ScholarshipLinkRequest.objects.get().pk])
        self.assertContains(r, 'Scholarships added by verified students')

    def test_it_never_rides_on_an_account_decision(self):
        self.add()
        self.user.verification_status = 'pending'
        self.user.save(update_fields=['verification_status'])

        r = self.office().get(QUEUE)
        for account in r.context['pending']:
            self.assertEqual(list(getattr(account, 'declarations', [])), [])

    def test_the_sidebar_badge_counts_them(self):
        self.add()
        r = self.office().get(QUEUE)
        self.assertEqual(r.context['pending_accounts'], 1)

    def approve(self, **extra):
        req = ScholarshipLinkRequest.objects.filter(status='Pending').first()
        data = {'declaration_id': req.id, 'action': 'approve', 'message': ''}
        data.update(extra)
        return self.office().post(QUEUE, data)

    def test_verifying_records_the_award(self):
        self.add()
        self.approve()

        req = ScholarshipLinkRequest.objects.get()
        self.assertEqual(req.status, 'Approved')
        self.assertEqual(req.reviewed_by, self.officer)

        award = Application.objects.get(student=self.profile)
        self.assertEqual(award.status, 'Approved')
        self.assertEqual(award.scholarship.type, 'DOST')
        self.assertEqual(award.school_year, '2026-2027')
        self.assertEqual(req.linked_application, award)

        self.assertEqual(held_scholarship_types(self.profile), {'DOST'})

    def test_the_award_reaches_my_applications(self):
        self.add()
        self.approve()
        r = self.student().get('/student/applications/')
        self.assertContains(r, 'DOST Scholarship')

    def test_verifying_claims_the_matching_imported_row(self):
        row = ImportedScholar.objects.create(
            scholarship_type='DOST', term_label=self.label,
            last_name='Dela Cruz', first_name='Juan', student_id='2022-0001',
            award_number='2026-DOST-00194', course='BSIT',
            imported_from='DOST_26-1.xlsx',
        )
        self.add()

        r = self.office().get(QUEUE)
        offered = r.context['added_scholarships'][0].archive_candidates
        self.assertEqual([c.pk for c in offered], [row.pk])

        req = ScholarshipLinkRequest.objects.get()
        self.approve(**{f'archive_id_{req.pk}': row.id})
        row.refresh_from_db()
        self.assertEqual(row.claimed_by, self.profile)
        self.assertEqual(ScholarshipLinkRequest.objects.get().matched_archive, row)

    def test_the_student_is_notified_either_way(self):
        self.add()
        self.approve()
        self.assertTrue(Notification.objects.filter(
            student=self.profile, type='success').exists())

        Notification.objects.all().delete()
        ScholarshipLinkRequest.objects.all().delete()
        Application.objects.all().delete()

        self.add()
        req = ScholarshipLinkRequest.objects.get()
        self.office().post(QUEUE, {
            'declaration_id': req.id, 'action': 'reject',
            'message': 'That award letter is from another university.'})

        req.refresh_from_db()
        self.assertEqual(req.status, 'Rejected')
        note = Notification.objects.get(student=self.profile)
        self.assertEqual(note.type, 'warning')
        self.assertIn('another university', note.body)

    def test_a_rejection_and_its_reason_come_back_to_my_profile(self):
        self.add()
        req = ScholarshipLinkRequest.objects.get()
        self.office().post(QUEUE, {
            'declaration_id': req.id, 'action': 'reject',
            'message': 'That award letter is from another university.'})

        r = self.student().get(PROFILE)
        self.assertContains(r, 'another university')
        self.assertEqual(r.context['scholarship_blocked_reason'], '')

    def test_turning_one_down_needs_a_reason(self):
        self.add()
        req = ScholarshipLinkRequest.objects.get()
        r = self.office().post(QUEUE, {
            'declaration_id': req.id, 'action': 'reject', 'message': '  '})

        self.assertIn('error=', r['Location'])
        req.refresh_from_db()
        self.assertEqual(req.status, 'Pending')

    def test_one_cannot_be_decided_twice(self):
        self.add()
        req_id = ScholarshipLinkRequest.objects.get().id
        self.approve()
        r = self.office().post(QUEUE, {
            'declaration_id': req_id, 'action': 'approve', 'message': ''})
        self.assertIn('no+longer', r['Location'])
        self.assertEqual(Application.objects.filter(student=self.profile).count(), 1)

    def test_a_ched_award_must_name_its_tier(self):
        r = self.add(scholarship_type='CHED', award_tier='')
        self.assertContains(r, 'Full Merit')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)

        self.add(scholarship_type='CHED', award_tier='Full')
        self.assertEqual(ScholarshipLinkRequest.objects.get().award_tier, 'Full')

    def test_the_officer_can_correct_the_ched_tier(self):
        self.add(scholarship_type='CHED', award_tier='Full')
        req = ScholarshipLinkRequest.objects.get()
        self.approve(**{f'award_tier_{req.pk}': 'Half'})

        req.refresh_from_db()
        self.assertEqual(req.award_tier, 'Half')
        self.assertEqual(req.linked_application.form_data['scholar_type'],
                         'Half Merit / Partial Scholar')

    def test_a_bad_proof_takes_the_whole_save_back(self):
        r = self.add(proof_document=a_proof('virus.exe'), suffix='Jr.')
        self.assertContains(r, 'Unsupported file type')
        self.assertFalse(r.context['saved'])
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.suffix, 'Jr.')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)

    def test_the_proof_is_validated_server_side(self):
        r = self.add(proof_document=a_proof(size=6 * 1024 * 1024))
        self.assertContains(r, 'too large')

        r = self.add(proof_document='')
        self.assertContains(r, 'Proof document is required')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)

    def test_a_post_that_names_no_scholarship_is_refused(self):
        r = self.add(scholarship_type='')
        self.assertContains(r, 'Say which scholarship you already hold')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)

    def test_the_card_closes_while_one_is_waiting(self):
        self.add()
        r = self.student().get(PROFILE)
        self.assertIn('still checking it', r.context['scholarship_blocked_reason'])
        self.add(scholarship_type='CHED', award_tier='Full')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 1)

    def test_the_card_closes_once_they_hold_something(self):
        self.add()
        self.approve()

        r = self.student().get(PROFILE)
        self.assertIn('already holds', r.context['scholarship_blocked_reason'])
        self.assertEqual(r.context['scholarship_types'], [])
        self.assertNotContains(r, 'I hold a scholarship the office has not recorded yet')

        self.add(scholarship_type='CHED', award_tier='Full')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 1)

    def test_signing_out_closes_my_profile(self):
        r = Client().get(PROFILE)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_a_student_cannot_decide_their_own(self):
        self.add()
        req = ScholarshipLinkRequest.objects.get()
        self.student().post(QUEUE, {
            'declaration_id': req.id, 'action': 'approve'})

        req.refresh_from_db()
        self.assertEqual(req.status, 'Pending')
        self.assertFalse(Application.objects.filter(student=self.profile).exists())

    def test_the_pages_it_replaced_are_gone(self):
        c = self.student()
        self.assertEqual(c.get('/student/add-scholarship/').status_code, 404)
        self.assertEqual(self.office().get('/vpsea/declarations/').status_code, 404)


class ProfileNotSetUpTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        User.objects.create_user(
            username='nobody@bipsu.edu.ph', email='nobody@bipsu.edu.ph',
            password='sekritpw123', role='student',
            verification_status='approved', email_verified=True,
        )

    def test_the_card_says_what_is_missing(self):
        c = Client()
        self.assertTrue(c.login(email='nobody@bipsu.edu.ph', password='sekritpw123'))
        r = c.get(PROFILE)
        self.assertEqual(r.status_code, 200)
        self.assertIn('not set up yet', r.context['scholarship_blocked_reason'])
