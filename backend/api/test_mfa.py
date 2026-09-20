"""Two-step sign-in for office accounts.

The point of the feature is that a correct password alone does not produce a
signed-in session, so most of these drive the real sign-in form and then ask
whether the client is authenticated — not whether the page mentioned a code.
"""

import base64

from django.test import Client, TestCase, override_settings

from api import mfa
from api.models import SystemSettings, User

RFC_SECRET = base64.b32encode(b'12345678901234567890').decode().rstrip('=')

RFC_VECTORS = (
    (59, '287082'),
    (1111111109, '081804'),
    (1111111111, '050471'),
    (1234567890, '005924'),
    (2000000000, '279037'),
)


class TotpAlgorithmTest(TestCase):

    def test_the_codes_match_the_rfc_6238_test_vectors(self):
        for at, expected in RFC_VECTORS:
            with self.subTest(at=at):
                self.assertEqual(mfa.code_now(RFC_SECRET, at=at), expected)

    def test_a_code_from_the_previous_step_is_still_accepted(self):
        earlier = mfa.code_now(RFC_SECRET, at=1111111109 - mfa.PERIOD)
        self.assertTrue(mfa.verify(RFC_SECRET, earlier, at=1111111109))

    def test_a_code_two_steps_old_is_refused(self):
        stale = mfa.code_now(RFC_SECRET, at=1111111109 - mfa.PERIOD * 3)
        self.assertFalse(mfa.verify(RFC_SECRET, stale, at=1111111109))

    def test_a_short_or_empty_answer_is_refused_without_raising(self):
        for answer in ('', None, '1234', 'abcdef', '12345678'):
            with self.subTest(answer=answer):
                self.assertFalse(mfa.verify(RFC_SECRET, answer, at=59))

    def test_a_damaged_secret_refuses_rather_than_raising(self):
        self.assertFalse(mfa.verify('not base32 at all!!', '287082', at=59))

    def test_two_fresh_secrets_differ(self):
        self.assertNotEqual(mfa.new_secret(), mfa.new_secret())

    def test_the_provisioning_uri_names_the_account_and_the_secret(self):
        uri = mfa.provisioning_uri('ABCD', 'vpsea@bipsu.edu.ph')
        self.assertTrue(uri.startswith('otpauth://totp/'))
        self.assertIn('secret=ABCD', uri)
        self.assertIn('vpsea%40bipsu.edu.ph', uri)

    def test_a_recovery_code_works_once_and_not_twice(self):
        codes = mfa.new_recovery_codes()
        stored = [mfa.hash_recovery_code(code) for code in codes]

        used, remaining = mfa.spend_recovery_code(stored, codes[0])
        self.assertTrue(used)
        self.assertEqual(len(remaining), len(stored) - 1)

        again, still = mfa.spend_recovery_code(remaining, codes[0])
        self.assertFalse(again)
        self.assertEqual(len(still), len(remaining))

    def test_a_recovery_code_is_never_stored_in_the_clear(self):
        codes = mfa.new_recovery_codes()
        stored = [mfa.hash_recovery_code(code) for code in codes]
        for code in codes:
            with self.subTest(code=code):
                self.assertNotIn(code, stored)

    def test_recovery_codes_are_matched_however_they_are_typed(self):
        code = mfa.new_recovery_codes(1)[0]
        stored = [mfa.hash_recovery_code(code)]
        spaced = f'{code[:5]} {code[5:]}'.lower()
        used, _remaining = mfa.spend_recovery_code(stored, spaced)
        self.assertTrue(used)


class OfficeEnrolmentTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.officer = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='office-pw-1', role='vpsea')
        self.client = Client()
        self.assertTrue(self.client.login(
            email='vpsea@bipsu.edu.ph', password='office-pw-1'))

    def test_enrolment_lives_on_the_profile_page_not_a_page_of_its_own(self):
        page = self.client.get('/vpsea/profile/')
        self.assertContains(page, 'Two-Step Sign-In')
        self.assertContains(page, 'name="action" value="mfa_start"')

    def test_starting_enrolment_issues_a_secret_but_does_not_turn_it_on(self):
        self.client.post('/vpsea/profile/', {'action': 'mfa_start'})
        self.officer.refresh_from_db()
        self.assertTrue(self.officer.mfa_secret)
        self.assertFalse(self.officer.mfa_enabled)

    def test_the_setup_key_is_shown_in_the_grouped_form_apps_ask_for(self):
        self.client.post('/vpsea/profile/', {'action': 'mfa_start'})
        self.officer.refresh_from_db()
        page = self.client.get('/vpsea/profile/')
        self.assertContains(page, mfa.format_secret(self.officer.mfa_secret))

    def test_a_wrong_code_does_not_turn_it_on(self):
        self.client.post('/vpsea/profile/', {'action': 'mfa_start'})
        self.client.post('/vpsea/profile/',
                         {'action': 'mfa_confirm', 'mfa_code': '000000'})
        self.officer.refresh_from_db()
        self.assertFalse(self.officer.mfa_enabled)

    def test_the_right_code_turns_it_on_and_shows_recovery_codes_once(self):
        self.client.post('/vpsea/profile/', {'action': 'mfa_start'})
        self.officer.refresh_from_db()

        page = self.client.post('/vpsea/profile/', {
            'action': 'mfa_confirm',
            'mfa_code': mfa.code_now(self.officer.mfa_secret),
        })
        self.officer.refresh_from_db()
        self.assertTrue(self.officer.mfa_enabled)
        self.assertEqual(len(self.officer.mfa_recovery_codes),
                         mfa.RECOVERY_CODE_COUNT)

        shown = [code for code in page.context['mfa_new_recovery_codes']]
        self.assertEqual(len(shown), mfa.RECOVERY_CODE_COUNT)
        self.assertNotContains(self.client.get('/vpsea/profile/'), shown[0])

    def test_turning_it_off_needs_the_current_password(self):
        self._enrol()
        self.client.post('/vpsea/profile/',
                         {'action': 'mfa_disable', 'current_password': 'wrong'})
        self.officer.refresh_from_db()
        self.assertTrue(self.officer.mfa_enabled)

        self.client.post('/vpsea/profile/',
                         {'action': 'mfa_disable',
                          'current_password': 'office-pw-1'})
        self.officer.refresh_from_db()
        self.assertFalse(self.officer.mfa_enabled)
        self.assertEqual(self.officer.mfa_secret, '')
        self.assertEqual(self.officer.mfa_recovery_codes, [])

    def _enrol(self):
        """Put this account through enrolment, as the office would."""
        self.client.post('/vpsea/profile/', {'action': 'mfa_start'})
        self.officer.refresh_from_db()
        self.client.post('/vpsea/profile/', {
            'action': 'mfa_confirm',
            'mfa_code': mfa.code_now(self.officer.mfa_secret),
        })
        self.officer.refresh_from_db()


class TwoStepSignInTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.officer = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='office-pw-1', role='vpsea')
        self.officer.begin_mfa_enrolment()
        self.recovery = self.officer.confirm_mfa(
            mfa.code_now(self.officer.mfa_secret))
        self.assertIsNotNone(self.recovery)
        self.client = Client()

    def _password_step(self):
        """Post the correct password and return the response."""
        return self.client.post('/login/', {
            'email': 'vpsea@bipsu.edu.ph', 'password': 'office-pw-1'})

    def _signed_in(self):
        """Whether the client now holds a signed-in session."""
        return self.client.session.get('_auth_user_id') is not None

    def test_the_right_password_alone_does_not_sign_the_office_in(self):
        response = self._password_step()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._signed_in())

    def test_the_password_step_asks_for_a_code_on_the_same_page(self):
        response = self._password_step()
        self.assertContains(response, 'name="mfa_code"')
        self.assertNotContains(response, 'name="password"')

    def test_the_code_completes_the_sign_in(self):
        self._password_step()
        response = self.client.post(
            '/login/', {'mfa_code': mfa.code_now(self.officer.mfa_secret)})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self._signed_in())

    def test_a_wrong_code_leaves_the_caller_signed_out(self):
        self._password_step()
        response = self.client.post('/login/', {'mfa_code': '000000'})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self._signed_in())

    def test_a_code_without_the_password_step_signs_nobody_in(self):
        response = self.client.post(
            '/login/', {'mfa_code': mfa.code_now(self.officer.mfa_secret)})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self._signed_in())

    def test_a_recovery_code_completes_the_sign_in_and_is_then_spent(self):
        self._password_step()
        self.client.post('/login/', {'mfa_code': self.recovery[0]})
        self.assertTrue(self._signed_in())

        self.officer.refresh_from_db()
        self.assertEqual(len(self.officer.mfa_recovery_codes),
                         mfa.RECOVERY_CODE_COUNT - 1)

    def test_a_spent_recovery_code_does_not_work_again(self):
        self._password_step()
        self.client.post('/login/', {'mfa_code': self.recovery[0]})
        self.client.logout()

        self._password_step()
        response = self.client.post('/login/', {'mfa_code': self.recovery[0]})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self._signed_in())

    def test_an_account_without_mfa_still_signs_in_in_one_step(self):
        User.objects.create_user(
            username='student@bipsu.edu.ph', email='student@bipsu.edu.ph',
            password='student-pw-1', role='student')
        response = self.client.post('/login/', {
            'email': 'student@bipsu.edu.ph', 'password': 'student-pw-1'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self._signed_in())

    def test_a_stale_challenge_sends_the_caller_back_to_the_password(self):
        from datetime import timedelta

        from django.utils import timezone

        from api.views_auth import PENDING_MFA_SINCE

        self._password_step()
        session = self.client.session
        session[PENDING_MFA_SINCE] = (
            timezone.now() - timedelta(seconds=mfa.PERIOD * 100)).isoformat()
        session.save()

        response = self.client.post(
            '/login/', {'mfa_code': mfa.code_now(self.officer.mfa_secret)})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self._signed_in())
        self.assertContains(response, 'name="password"', status_code=401)


class EnforcementTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='office-pw-1', role='vpsea')
        self.client = Client()
        self.client.login(email='vpsea@bipsu.edu.ph', password='office-pw-1')

    def test_office_accounts_are_the_ones_mfa_is_required_of(self):
        officer = User.objects.get(email='vpsea@bipsu.edu.ph')
        student = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph',
            password='pw', role='student')
        self.assertTrue(officer.mfa_required)
        self.assertFalse(student.mfa_required)

    @override_settings(MFA_ENFORCED=False)
    def test_unenforced_the_office_reaches_its_records_as_before(self):
        self.assertEqual(self.client.get('/vpsea/archives/').status_code, 200)

    @override_settings(MFA_ENFORCED=True)
    def test_enforced_an_unenrolled_office_account_is_sent_to_enrol(self):
        response = self.client.get('/vpsea/archives/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/vpsea/profile/', response['Location'])

    @override_settings(MFA_ENFORCED=True)
    def test_enforced_the_profile_page_itself_stays_reachable(self):
        self.assertEqual(self.client.get('/vpsea/profile/').status_code, 200)

    @override_settings(MFA_ENFORCED=True)
    def test_enforced_an_enrolled_office_account_is_let_through(self):
        officer = User.objects.get(email='vpsea@bipsu.edu.ph')
        officer.begin_mfa_enrolment()
        officer.confirm_mfa(mfa.code_now(officer.mfa_secret))
        self.assertEqual(self.client.get('/vpsea/archives/').status_code, 200)
