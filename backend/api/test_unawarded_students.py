"""The archives tab for students the system has not served.

Every other archives tab answers "who holds scholarship X this term", so a
student holding nothing appears on none of them. This tab answers the office's
other question, and splits it by what the office would actually have to do:
invite someone who never applied, clear the queue for someone waiting, follow up
a rejection, nudge a draft that was never submitted.

It asks that only of students the office has verified. An account still in the
registration queue, or turned away from it, cannot sign in to apply at all, so
it is a decision owed on the accounts screen rather than a student to invite.
"""
from django.test import Client, TestCase

from api.models import (
    Application, Scholarship, StudentProfile, SystemSettings, User,
)

TAB = 'No Scholarship'


class UnawardedStudentsTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[],
        )
        User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))

    def _student(self, last, sid, gwa=0.0):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph', password='pw',
            first_name='Test', last_name=last, role='student',
        )
        return StudentProfile.objects.create(
            user=u, student_id=sid, course='BSCS', year_level=2, gwa=gwa)

    def _app(self, profile, status, term='26-1'):
        return Application.objects.create(
            student=profile, scholarship=Scholarship.objects.get(type='Academic'),
            status=status, term_label=term,
        )

    def _rows(self, sy=None):
        url = f'/vpsea/archives/?type={TAB}' + (f'&sy={sy}' if sy else '')
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200)
        return r

    # ── who appears ─────────────────────────────────────────────────────────

    def test_the_tab_is_offered_alongside_the_programmes(self):
        r = self.c.get('/vpsea/archives/?type=Academic')
        self.assertIn(TAB, r.context['archive_types'])

    def test_a_student_with_an_approved_award_is_not_listed(self):
        awarded = self._student('Santos', '2024-0001')
        self._app(awarded, 'Approved')
        self._student('Reyes', '2024-0002')

        rows = self._rows().context['rows']
        self.assertEqual([r['profile'].student_id for r in rows], ['2024-0002'])

    def test_an_award_in_another_term_does_not_count_for_this_one(self):
        """A scholar who was not renewed this semester is exactly who this is for."""
        lapsed = self._student('Cruz', '2024-0003')
        self._app(lapsed, 'Approved', term='25-2')

        rows = self._rows().context['rows']
        self.assertEqual([r['profile'].student_id for r in rows], ['2024-0003'])

    def test_an_account_the_office_rejected_is_not_listed(self):
        """Rejected at registration is not "unserved". That person was turned
        away at the door and cannot sign in to apply at all, so listing them
        here as a student to follow up misreads what the office decided."""
        turned_away = self._student('Ilagan', '2024-0080')
        turned_away.user.decide_verification('rejected', 'Not on our enrolment list.', None)
        self._student('Jimenez', '2024-0081')

        ctx = self._rows().context
        self.assertEqual([r['profile'].student_id for r in ctx['rows']], ['2024-0081'])
        self.assertEqual(ctx['total'], 1)

    def test_an_account_still_waiting_on_review_is_not_listed(self):
        """Pending is not "unserved" either. Nobody can sign in until the office
        decides, so a queued registrant has no way to apply, and this tab would
        be telling the office to invite someone it has not admitted yet. What
        that account is owed is a decision on the accounts screen."""
        waiting = self._student('Kalaw', '2024-0082')
        waiting.user.verification_status = 'pending'
        waiting.user.save(update_fields=['verification_status'])
        self._student('Lopez', '2024-0083')

        ctx = self._rows().context
        self.assertEqual([r['profile'].student_id for r in ctx['rows']], ['2024-0083'])
        self.assertEqual(ctx['total'], 1)

    def test_the_account_appears_once_the_office_approves_it(self):
        """The exclusion is about the queue, not the person — approving the
        account is what turns them into a student the office can invite."""
        waiting = self._student('Kalaw', '2024-0084')
        waiting.user.verification_status = 'pending'
        waiting.user.save(update_fields=['verification_status'])
        self.assertEqual(self._rows().context['total'], 0)

        waiting.user.decide_verification('approved', '', None)
        rows = self._rows().context['rows']
        self.assertEqual([r['profile'].student_id for r in rows], ['2024-0084'])

    def test_an_unconfirmed_address_does_not_hide_a_verified_student(self):
        """Never opening the confirmation link says nothing about whether the
        office can serve them — they can sign in and apply. It only means email
        will not reach them, which is the accounts screen's warning to give."""
        student = self._student('Marquez', '2024-0085')
        student.user.email_verified = False
        student.user.save(update_fields=['email_verified'])

        rows = self._rows().context['rows']
        self.assertEqual([r['profile'].student_id for r in rows], ['2024-0085'])

    # ── why they appear ─────────────────────────────────────────────────────

    def test_each_row_says_what_the_office_would_have_to_do(self):
        self._student('Abad', '2024-0010')          # never applied
        pending = self._student('Bello', '2024-0011')
        revising = self._student('Cruz', '2024-0012')
        rejected = self._student('Dizon', '2024-0013')
        self._app(pending, 'Pending Validation')
        self._app(revising, 'Needs Revision')
        self._app(rejected, 'Rejected')

        ctx = self._rows().context
        states = {r['profile'].student_id: r['state'] for r in ctx['rows']}
        self.assertEqual(states, {
            '2024-0010': 'never',
            '2024-0011': 'pending',
            # Sent back for a correction is still waiting on the student, which
            # from this tab's point of view is the same as pending.
            '2024-0012': 'pending',
            '2024-0013': 'rejected',
        })
        self.assertEqual(ctx['total'], 4)

        # Unused rows are dropped, so the student's own name reaches the page.
        self.assertContains(self._rows(), 'Abad')

    def test_the_most_recent_application_is_the_one_reported(self):
        student = self._student('Ramos', '2024-0020')
        self._app(student, 'Rejected', term='25-2')
        self._app(student, 'Pending Validation', term='26-1')

        row = self._rows().context['rows'][0]
        self.assertEqual(row['state'], 'pending')

    def test_a_qualifying_gwa_is_surfaced_so_the_office_can_invite_them(self):
        self._student('Uy', '2024-0030', gwa=1.20)
        self._student('Villa', '2024-0031', gwa=2.80)

        by_id = {r['profile'].student_id: r for r in self._rows().context['rows']}
        self.assertEqual(by_id['2024-0030']['classification'], 'University Scholar')
        self.assertEqual(by_id['2024-0031']['classification'], 'Not Eligible')

    # ── boundaries ──────────────────────────────────────────────────────────

    def test_the_tab_is_closed_to_other_offices(self):
        User.objects.create_user(
            username='staff@bipsu.edu.ph', email='staff@bipsu.edu.ph',
            password='pw', role='nsu_staff',
        )
        other = Client()
        self.assertTrue(other.login(email='staff@bipsu.edu.ph', password='pw'))
        r = other.get(f'/vpsea/archives/?type={TAB}')
        self.assertNotEqual(r.status_code, 200)

    # ── editing ─────────────────────────────────────────────────────────────

    def test_the_office_can_correct_a_students_details_from_this_tab(self):
        """The point of the tab: these students have accounts, and the office
        fixes their typos here rather than hunting for them elsewhere."""
        student = self._student('Delacruz', '2024-0050')
        r = self.c.post(f'/vpsea/archives/student/{student.pk}/edit/', {
            'first_name': 'Maria', 'last_name': 'Dela Cruz',
            'student_id': '2024-0050', 'gender': 'Female',
            'course': 'BSIT', 'year_level': '3', 'gwa': '1.45',
            'contact_number': '09171234567',
            'barangay': 'Poblacion', 'municipality': 'Naval', 'province': 'Biliran',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn('edited=1', r['Location'])

        student.refresh_from_db()
        student.user.refresh_from_db()
        self.assertEqual(student.user.first_name, 'Maria')
        self.assertEqual(student.user.last_name, 'Dela Cruz')
        self.assertEqual(student.course, 'BSIT')
        self.assertEqual(student.year_level, 3)
        self.assertEqual(student.gwa, 1.45)
        self.assertEqual(student.contact_number, '09171234567')
        self.assertEqual(student.municipality, 'Naval')

    def test_a_student_number_already_in_use_is_refused_with_a_reason(self):
        taken = self._student('Owner', '2024-0060')
        other = self._student('Borrower', '2024-0061')
        r = self.c.post(f'/vpsea/archives/student/{other.pk}/edit/', {
            'first_name': 'B', 'last_name': 'Borrower',
            'student_id': taken.student_id, 'course': 'BSCS', 'year_level': '1',
        })
        self.assertIn('error=', r['Location'])
        other.refresh_from_db()
        self.assertEqual(other.student_id, '2024-0061')

    def test_the_edit_endpoint_is_closed_to_other_offices(self):
        student = self._student('Locked', '2024-0070')
        User.objects.create_user(
            username='staff2@bipsu.edu.ph', email='staff2@bipsu.edu.ph',
            password='pw', role='nsu_staff',
        )
        other = Client()
        self.assertTrue(other.login(email='staff2@bipsu.edu.ph', password='pw'))
        other.post(f'/vpsea/archives/student/{student.pk}/edit/',
                   {'first_name': 'Hacked', 'last_name': 'Nope', 'course': 'X', 'year_level': '1'})
        student.user.refresh_from_db()
        self.assertNotEqual(student.user.first_name, 'Hacked')

    # ── deleting ────────────────────────────────────────────────────────────

    def test_the_office_can_delete_a_student_from_this_tab(self):
        """Editing was the only action here, so a duplicate or a mistyped
        registration could be corrected but never removed."""
        student = self._student('Ghost', '2024-0100')
        keep = self._student('Stays', '2024-0101')
        user_pk = student.user.pk

        r = self.c.post(f'/vpsea/archives/student/{student.pk}/delete/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('deleted=1', r['Location'])

        self.assertFalse(StudentProfile.objects.filter(pk=student.pk).exists())
        self.assertFalse(User.objects.filter(pk=user_pk).exists())
        self.assertTrue(StudentProfile.objects.filter(pk=keep.pk).exists())

    def test_deleting_takes_the_applications_with_it(self):
        student = self._student('Trail', '2024-0102')
        self._app(student, 'Rejected')

        self.c.post(f'/vpsea/archives/student/{student.pk}/delete/')
        self.assertEqual(Application.objects.count(), 0)

    def test_a_get_deletes_nobody(self):
        """A link that deletes on GET is one crawler, or one mistyped URL, away
        from taking a student out."""
        student = self._student('Safe', '2024-0103')
        r = self.c.get(f'/vpsea/archives/student/{student.pk}/delete/')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(StudentProfile.objects.filter(pk=student.pk).exists())

    def test_deleting_a_student_who_is_already_gone_is_not_an_error(self):
        student = self._student('Twice', '2024-0104')
        pk = student.pk
        self.c.post(f'/vpsea/archives/student/{pk}/delete/')
        r = self.c.post(f'/vpsea/archives/student/{pk}/delete/')
        self.assertEqual(r.status_code, 302)

    def test_the_delete_endpoint_is_closed_to_other_offices(self):
        student = self._student('Guarded', '2024-0105')
        User.objects.create_user(
            username='staff3@bipsu.edu.ph', email='staff3@bipsu.edu.ph',
            password='pw', role='nsu_staff',
        )
        other = Client()
        self.assertTrue(other.login(email='staff3@bipsu.edu.ph', password='pw'))
        other.post(f'/vpsea/archives/student/{student.pk}/delete/')
        self.assertTrue(StudentProfile.objects.filter(pk=student.pk).exists())

    def test_the_row_offers_the_delete_action(self):
        student = self._student('Listed', '2024-0106')
        r = self._rows()
        self.assertContains(r, f'/vpsea/archives/student/{student.pk}/delete/')
        # Asked through the portal's own confirm dialog, not window.confirm.
        self.assertContains(r, 'data-confirm-tone="danger"')

    # ── the empty state ─────────────────────────────────────────────────────

    def test_the_page_holds_up_when_nobody_is_unawarded(self):
        awarded = self._student('Solo', '2024-0040')
        self._app(awarded, 'Approved')

        r = self._rows()
        self.assertEqual(r.context['total'], 0)
        self.assertContains(r, 'Every student on file holds an approved scholarship')


class StudentsScreenNoScholarshipTabTest(TestCase):
    """The students screen asks the same question on its own tab.

    Hiding a rejected registrant from the archives is no use if the office
    finds them again one page over, so the two listings agree on who counts.
    """

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[],
        )
        User.objects.create_user(
            username='vpsea2@bipsu.edu.ph', email='vpsea2@bipsu.edu.ph',
            password='pw', role='vpsea',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='vpsea2@bipsu.edu.ph', password='pw'))

    def _student(self, last, sid):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph', password='pw',
            first_name='Test', last_name=last, role='student',
        )
        return StudentProfile.objects.create(
            user=u, student_id=sid, course='BSCS', year_level=2)

    def test_a_rejected_registrant_is_left_off_the_tab(self):
        turned_away = self._student('Ilagan', '2024-0090')
        turned_away.user.decide_verification('rejected', 'Not on our enrolment list.', None)
        self._student('Jimenez', '2024-0091')

        r = self.c.get('/vpsea/students/?tab=no_scholarship')
        self.assertEqual(r.status_code, 200)
        listed = [p.student_id for p in r.context['no_scholarship_students']]
        self.assertEqual(listed, ['2024-0091'])

    def test_a_registrant_still_in_the_queue_is_left_off_the_tab(self):
        waiting = self._student('Kalaw', '2024-0092')
        waiting.user.verification_status = 'pending'
        waiting.user.save(update_fields=['verification_status'])
        self._student('Lopez', '2024-0093')

        r = self.c.get('/vpsea/students/?tab=no_scholarship')
        listed = [p.student_id for p in r.context['no_scholarship_students']]
        self.assertEqual(listed, ['2024-0093'])
