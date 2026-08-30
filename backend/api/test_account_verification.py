"""A self-registered account cannot sign in until the SDSO releases it.

The person is never emailed — this project has no mail configured — so the login
page is the channel that reaches someone who cannot get in yet. Every test here
is really about that: does the right message reach the right person.
"""
from django.test import Client, TestCase

from api.models import Notification, StaffProfile, StudentProfile, User


class RegistrationLeavesTheAccountPendingTest(TestCase):
    def setUp(self):
        self.c = Client()

    def _register(self, **overrides):
        data = {
            'account_type': 'student',
            'first_name': 'Juan', 'last_name': 'Dela Cruz',
            'email': 'juan@bipsu.edu.ph',
            'password': 'demo1234', 'confirm_password': 'demo1234',
            'student_id': '2022-00999',
            'school': 'School of Technologies and Computer Studies', 'course': 'BSCS',
            'year_level': '2',
        }
        data.update(overrides)
        return self.c.post('/register/', data, follow=True)

    def test_a_new_student_is_pending_and_not_signed_in(self):
        r = self._register()
        user = User.objects.get(email='juan@bipsu.edu.ph')
        self.assertEqual(user.verification_status, 'pending')
        self.assertFalse(user.can_sign_in)
        self.assertNotIn('_auth_user_id', self.c.session)
        self.assertContains(r, 'Registration received')

    def test_a_new_staff_is_pending_too(self):
        self._register(account_type='nsu_staff', email='staff@bipsu.edu.ph')
        self.assertEqual(
            User.objects.get(email='staff@bipsu.edu.ph').verification_status, 'pending')

    def test_the_landing_page_says_what_happens_next(self):
        r = self._register()
        self.assertContains(r, 'to verify your account')
        self.assertContains(r, 'will not have to sign in again')
        self.assertContains(r, 'juan@bipsu.edu.ph')
        self.assertContains(r, 'href="/login/"')

    def test_an_account_the_office_creates_is_verified_already(self):
        office = User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph', password='pw',
            first_name='Rosario', last_name='Bayhon', role='vpsea',
        )
        self.assertTrue(office.can_sign_in)


class SigningInWhileUnverifiedTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student',
            verification_status='pending',
        )
        StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS', year_level=2)
        self.c = Client()

    def _sign_in(self, password='pw', email='ana@bipsu.edu.ph'):
        return self.c.post('/login/', {'email': email, 'password': password})

    def test_pending_is_told_where_it_stands_and_stays_out(self):
        r = self._sign_in()
        self.assertContains(r, 'waiting for verification')
        self.assertNotIn('_auth_user_id', self.c.session)

    def test_rejected_reads_the_office_reason(self):
        self.user.decide_verification('rejected', 'Student ID is not on our enrolment list.', None)
        r = self._sign_in()
        self.assertContains(r, 'was not accepted')
        self.assertContains(r, 'not on our enrolment list')
        self.assertNotIn('_auth_user_id', self.c.session)

    def test_verified_signs_straight_into_the_portal(self):
        self.user.decide_verification('approved', '', None)
        r = self._sign_in()
        self.assertRedirects(r, '/student/applications/', fetch_redirect_response=False)
        self.assertIn('_auth_user_id', self.c.session)

    def test_a_wrong_password_never_reveals_the_account_standing(self):
        r = self._sign_in(password='not-the-password')
        self.assertContains(r, 'password does not match')
        self.assertNotContains(r, 'waiting for verification')

    def test_an_unknown_address_says_so_rather_than_blaming_the_password(self):
        r = self._sign_in(email='nobody@bipsu.edu.ph')
        self.assertContains(r, 'No account is registered')
        self.assertContains(r, 'Register an account')

    def test_a_wrong_password_keeps_the_address_on_the_form(self):
        r = self._sign_in(password='not-the-password')
        self.assertContains(r, self.user.email)


class SDSOVerificationQueueTest(TestCase):
    def setUp(self):
        self.officer = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph', password='pw',
            first_name='Rosario', last_name='Bayhon', role='vpsea',
        )
        self.student = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student',
            verification_status='pending',
        )
        self.profile = StudentProfile.objects.create(
            user=self.student, student_id='2022-00111', course='BSCS', year_level=2)
        self.c = Client()
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))

    def _decide(self, action, message=''):
        return self.c.post('/vpsea/accounts/',
                           {'user_id': self.student.id, 'action': action, 'message': message})

    def test_the_queue_shows_what_the_account_claimed_about_itself(self):
        r = self.c.get('/vpsea/accounts/')
        self.assertContains(r, 'ana@bipsu.edu.ph')
        self.assertContains(r, '2022-00111')
        self.assertContains(r, 'BSCS')

    def test_verifying_releases_the_account_and_records_who_did_it(self):
        self._decide('approve')
        self.student.refresh_from_db()
        self.assertEqual(self.student.verification_status, 'approved')
        self.assertTrue(self.student.can_sign_in)
        self.assertEqual(self.student.verified_by, self.officer)
        self.assertIsNotNone(self.student.verified_at)

    def test_verifying_leaves_a_notification_waiting_in_their_portal(self):
        self._decide('approve')
        note = Notification.objects.get(student=self.profile)
        self.assertEqual(note.title, 'Account verified')
        self.assertEqual(note.type, 'success')

    def test_an_approval_without_a_message_still_says_something_useful(self):
        self._decide('approve')
        self.student.refresh_from_db()
        self.assertIn('verified by the SDSO', self.student.verification_note)

    def test_rejecting_without_a_reason_is_refused(self):
        r = self._decide('reject')
        self.assertIn('reason+is+required', r['Location'])
        self.student.refresh_from_db()
        self.assertEqual(self.student.verification_status, 'pending')

    def test_the_rejection_reason_is_what_the_person_will_read(self):
        self._decide('reject', 'We have no record of that student number.')
        self.student.refresh_from_db()
        self.assertEqual(self.student.verification_status, 'rejected')
        self.assertEqual(self.student.verification_note,
                         'We have no record of that student number.')

    def test_a_rejected_account_can_be_released_later(self):
        self._decide('reject', 'Sent the wrong ID.')
        self._decide('approve', 'ID checked out on second look.')
        self.student.refresh_from_db()
        self.assertTrue(self.student.can_sign_in)

    def test_office_accounts_are_not_in_reach_of_this_page(self):
        other_officer = User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph', password='pw',
            role='unifast',
        )
        r = self.c.post('/vpsea/accounts/',
                        {'user_id': other_officer.id, 'action': 'reject', 'message': 'no'})
        self.assertIn('not+found', r['Location'])
        other_officer.refresh_from_db()
        self.assertTrue(other_officer.can_sign_in)

    def test_a_student_cannot_reach_the_queue(self):
        self.c.logout()
        self.student.verification_status = 'approved'
        self.student.save()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))
        r = self.c.get('/vpsea/accounts/')
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('/vpsea/', r['Location'])


class StaffVerificationTest(TestCase):
    """Staff have no StudentProfile, so the login page is their whole channel."""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph', password='pw',
            role='vpsea',
        )
        self.staff = User.objects.create_user(
            username='earl@bipsu.edu.ph', email='earl@bipsu.edu.ph', password='pw',
            first_name='Earl', last_name='Reyes', role='nsu_staff',
            verification_status='pending',
        )
        StaffProfile.objects.create(user=self.staff, employee_id='32-1-213313',
                                    department='School of Engineering')
        self.c = Client()
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))

    def test_the_queue_shows_the_employment_details_for_a_staff_account(self):
        r = self.c.get('/vpsea/accounts/')
        self.assertContains(r, '32-1-213313')
        self.assertContains(r, 'School of Engineering')

    def test_verifying_staff_does_not_blow_up_on_the_missing_student_profile(self):
        r = self.c.post('/vpsea/accounts/',
                        {'user_id': self.staff.id, 'action': 'approve', 'message': ''})
        self.assertEqual(r.status_code, 302)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.can_sign_in)
        self.assertEqual(Notification.objects.count(), 0)

    def test_verified_staff_reach_their_own_portal(self):
        self.staff.decide_verification('approved', '', self.officer)
        c = Client()
        r = c.post('/login/', {'email': 'earl@bipsu.edu.ph', 'password': 'pw'})
        self.assertRedirects(r, '/nsu-staff/', fetch_redirect_response=False)


class ReleasedWithoutTypingAgainTest(TestCase):
    """The whole point of the waiting room: verification lets them in by itself.

    The browser that registered is left holding a session that knows who they
    are, so the moment the SDSO releases the account any page view signs them
    in — no second trip through the login form.
    """

    def setUp(self):
        self.c = Client()
        self.c.post('/register/', {
            'account_type': 'student',
            'first_name': 'Juan', 'last_name': 'Dela Cruz',
            'email': 'juan@bipsu.edu.ph',
            'password': 'demo1234', 'confirm_password': 'demo1234',
            'student_id': '2022-00999',
            'school': 'School of Technologies and Computer Studies', 'course': 'BSCS',
            'year_level': '2',
        })
        self.user = User.objects.get(email='juan@bipsu.edu.ph')
        self.officer = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph', password='pw',
            role='vpsea',
        )

    def test_the_waiting_room_holds_while_the_account_is_pending(self):
        r = self.c.get('/register/received/')
        self.assertContains(r, 'to verify your account')
        self.assertContains(r, 'http-equiv="refresh"')
        self.assertNotIn('_auth_user_id', self.c.session)

    def test_verifying_signs_them_in_on_the_next_page_view(self):
        self.user.decide_verification('approved', '', self.officer)
        r = self.c.get('/register/received/')
        self.assertRedirects(r, '/student/applications/', fetch_redirect_response=False)
        self.assertIn('_auth_user_id', self.c.session)

    def test_any_page_releases_them_not_just_the_waiting_room(self):
        self.user.decide_verification('approved', '', self.officer)
        self.c.get('/')                       # they wandered back to the home page
        self.assertIn('_auth_user_id', self.c.session)

    def test_the_login_page_does_not_ask_someone_already_let_in_to_type(self):
        self.user.decide_verification('approved', '', self.officer)
        r = self.c.get('/login/')
        self.assertRedirects(r, '/student/applications/', fetch_redirect_response=False)

    def test_a_rejection_reaches_them_where_they_are_waiting(self):
        self.user.decide_verification('rejected', 'Student ID is not on our list.', self.officer)
        r = self.c.get('/register/received/')
        self.assertContains(r, 'was not accepted')
        self.assertContains(r, 'not on our list')
        self.assertNotContains(r, 'http-equiv="refresh"')
        self.assertNotIn('_auth_user_id', self.c.session)

    def test_a_rejected_account_is_never_let_in_by_the_middleware(self):
        self.user.decide_verification('rejected', 'No record of that ID.', self.officer)
        self.c.get('/')
        self.assertNotIn('_auth_user_id', self.c.session)

    def test_the_free_pass_expires_so_a_shared_computer_stays_safe(self):
        from datetime import timedelta
        from django.utils import timezone
        from api.middleware import PENDING_EMAIL, PENDING_SINCE

        session = self.c.session
        session[PENDING_SINCE] = (timezone.now() - timedelta(days=8)).isoformat()
        session.save()

        self.user.decide_verification('approved', '', self.officer)
        self.c.get('/')
        self.assertNotIn('_auth_user_id', self.c.session)
        # The stale claim is dropped rather than left to linger.
        self.assertNotIn(PENDING_EMAIL, self.c.session)

    def test_a_browser_that_never_registered_is_left_alone(self):
        c = Client()
        self.user.decide_verification('approved', '', self.officer)
        c.get('/')
        self.assertNotIn('_auth_user_id', c.session)
