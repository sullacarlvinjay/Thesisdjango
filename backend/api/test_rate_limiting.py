from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from api.models import StudentProfile, SystemSettings, User


REAL_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'throttle-tests',
    },
}


@override_settings(CACHES=REAL_CACHE)
class LoginThrottleTest(TestCase):
    """Repeated wrong passwords must stop being answered.

    Settings pin the test cache to a dummy backend, which forgets everything
    written to it. A throttle tested against that backend would pass whether or
    not it counted anything, so these cases supply a real one.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='right-password', first_name='Ana', last_name='Lim',
            role='student', verification_status='approved')
        StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS',
            year_level=2)
        self.c = Client()

    def _attempt(self, password='wrong-password', email='ana@bipsu.edu.ph'):
        return self.c.post('/login/', {'email': email, 'password': password})

    def test_a_handful_of_wrong_passwords_are_still_answered_normally(self):
        for _ in range(7):
            self.assertEqual(self._attempt().status_code, 401)

    def test_the_ninth_wrong_password_is_refused_outright(self):
        for _ in range(8):
            self._attempt()
        refused = self._attempt()
        self.assertEqual(refused.status_code, 429)
        self.assertContains(refused, 'Too many sign-in attempts',
                            status_code=429)

    def test_the_lockout_survives_a_switch_to_the_correct_password(self):
        for _ in range(8):
            self._attempt()
        blocked = self._attempt(password='right-password')
        self.assertEqual(blocked.status_code, 429)
        self.assertNotIn('_auth_user_id', self.c.session)

    def test_a_good_sign_in_before_the_limit_clears_the_tally(self):
        for _ in range(5):
            self._attempt()
        self._attempt(password='right-password')
        self.assertIn('_auth_user_id', self.c.session)
        self.c.logout()
        for _ in range(7):
            self.assertEqual(self._attempt().status_code, 401)

    def test_the_account_is_protected_even_when_the_address_changes(self):
        for n in range(8):
            self.c.post('/login/',
                        {'email': 'ana@bipsu.edu.ph', 'password': 'x'},
                        REMOTE_ADDR=f'10.0.0.{n}')
        refused = self.c.post('/login/',
                              {'email': 'ana@bipsu.edu.ph', 'password': 'x'},
                              REMOTE_ADDR='10.0.0.200')
        self.assertEqual(
            refused.status_code, 429,
            'spreading attempts over many addresses defeated the throttle')

    def test_one_locked_account_does_not_lock_a_different_one(self):
        User.objects.create_user(
            username='ben@bipsu.edu.ph', email='ben@bipsu.edu.ph',
            password='pw', first_name='Ben', last_name='Cruz', role='student')
        for n in range(9):
            self.c.post('/login/',
                        {'email': 'ana@bipsu.edu.ph', 'password': 'x'},
                        REMOTE_ADDR=f'10.1.0.{n}')
        other = self.c.post('/login/',
                            {'email': 'ben@bipsu.edu.ph', 'password': 'x'},
                            REMOTE_ADDR='10.1.0.250')
        self.assertEqual(other.status_code, 401)

    def test_an_empty_form_is_not_counted_against_the_caller(self):
        for _ in range(12):
            self.c.post('/login/', {'email': '', 'password': ''})
        self.assertEqual(self._attempt().status_code, 401)


@override_settings(CACHES=REAL_CACHE)
class RegistrationThrottleTest(TestCase):
    """The register form must not be drivable in bulk.

    Counting only rejected submissions would miss the abuse that matters: a
    script that submits valid forms mints accounts and sends university mail to
    every address it is given.
    """

    def setUp(self):
        cache.clear()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        self.c = Client()

    def _submit(self, n):
        return self.c.post('/register/', {
            'account_type': 'student',
            'email': f'applicant{n}@bipsu.edu.ph',
            'first_name': 'A', 'last_name': 'B',
        })

    def test_the_sixth_submission_from_one_caller_is_refused(self):
        for n in range(5):
            self.assertNotEqual(self._submit(n).status_code, 429)
        self.assertEqual(self._submit(99).status_code, 429)

    def test_the_refusal_explains_the_wait(self):
        for n in range(5):
            self._submit(n)
        self.assertContains(self._submit(99), 'Too many registrations',
                            status_code=429)


@override_settings(CACHES=REAL_CACHE)
class ThrottleAddressTest(TestCase):
    """Which address the throttle counts against."""

    def setUp(self):
        cache.clear()

    def test_the_forwarded_header_is_read_when_a_proxy_is_trusted(self):
        from api import ratelimit
        request = type('R', (), {'META': {
            'HTTP_X_FORWARDED_FOR': '203.0.113.9, 10.0.0.1',
            'REMOTE_ADDR': '10.0.0.1'}})()
        with override_settings(TRUST_FORWARDED_FOR=True):
            self.assertEqual(ratelimit.client_address(request), '203.0.113.9')

    def test_the_forwarded_header_is_ignored_when_no_proxy_is_trusted(self):
        from api import ratelimit
        request = type('R', (), {'META': {
            'HTTP_X_FORWARDED_FOR': '203.0.113.9',
            'REMOTE_ADDR': '10.0.0.1'}})()
        with override_settings(TRUST_FORWARDED_FOR=False):
            self.assertEqual(
                ratelimit.client_address(request), '10.0.0.1',
                'an untrusted caller could pick their own throttle bucket')


@override_settings(CACHES=REAL_CACHE)
class ApiCredentialThrottleTest(TestCase):
    """The REST endpoints spend the same allowance as the web forms.

    ``/login/`` and ``/api/auth/login/`` reach the same accounts with the same
    passwords. Counted separately they are two allowances on one account, and
    the published OpenAPI schema tells an attacker where the unguarded one is.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='right-password', first_name='Ana', last_name='Lim',
            role='student', verification_status='approved')
        StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS',
            year_level=2)
        self.c = Client()

    def _api(self, password='wrong-password', email='ana@bipsu.edu.ph'):
        return self.c.post('/api/auth/login/',
                           {'email': email, 'password': password},
                           content_type='application/json')

    def _form(self, password='wrong-password', email='ana@bipsu.edu.ph'):
        return self.c.post('/login/', {'email': email, 'password': password})

    def test_a_handful_of_wrong_passwords_are_still_answered_normally(self):
        for _ in range(7):
            self.assertEqual(self._api().status_code, 400)

    def test_the_ninth_wrong_password_is_refused_outright(self):
        for _ in range(8):
            self._api()
        self.assertEqual(self._api().status_code, 429)

    def test_the_refusal_explains_the_wait_and_says_when_to_return(self):
        for _ in range(8):
            self._api()
        refused = self._api()
        self.assertIn('Too many sign-in attempts',
                      refused.json().get('detail', ''))
        self.assertTrue(
            refused.headers.get('Retry-After'),
            'a throttled client was told to wait but not for how long')

    def test_attempts_at_the_form_lock_the_endpoint(self):
        for _ in range(8):
            self._form()
        self.assertEqual(
            self._api().status_code, 429,
            'the endpoint handed out a fresh allowance the form had spent')

    def test_attempts_at_the_endpoint_lock_the_form(self):
        for _ in range(8):
            self._api()
        self.assertEqual(
            self._form().status_code, 429,
            'the form handed out a fresh allowance the endpoint had spent')

    def test_the_lockout_survives_a_switch_to_the_correct_password(self):
        for _ in range(8):
            self._api()
        blocked = self._api(password='right-password')
        self.assertEqual(blocked.status_code, 429)
        self.assertNotIn('token', blocked.json())

    def test_a_good_sign_in_before_the_limit_clears_the_tally(self):
        for _ in range(5):
            self._api()
        self.assertEqual(self._api(password='right-password').status_code, 200)
        for _ in range(7):
            self.assertEqual(self._api().status_code, 400)

    def test_the_account_is_protected_even_when_the_address_changes(self):
        for n in range(8):
            self.c.post('/api/auth/login/',
                        {'email': 'ana@bipsu.edu.ph', 'password': 'x'},
                        content_type='application/json',
                        REMOTE_ADDR=f'10.0.0.{n}')
        refused = self.c.post('/api/auth/login/',
                              {'email': 'ana@bipsu.edu.ph', 'password': 'x'},
                              content_type='application/json',
                              REMOTE_ADDR='10.0.0.200')
        self.assertEqual(
            refused.status_code, 429,
            'spreading attempts over many addresses defeated the throttle')

    def test_a_body_that_is_not_an_object_is_still_counted_by_address(self):
        for _ in range(8):
            self.c.post('/api/auth/login/', '[]',
                        content_type='application/json')
        self.assertEqual(self._api().status_code, 429)


@override_settings(CACHES=REAL_CACHE)
class ApiRegistrationThrottleTest(TestCase):
    """The register endpoint must not be drivable in bulk either.

    This is the one that mints accounts and sends university mail to whatever
    address it is handed, so it is the submissions that *succeed* that need
    counting.
    """

    def setUp(self):
        cache.clear()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        self.c = Client()

    def _submit(self, n):
        return self.c.post('/api/auth/register/', {
            'email': f'applicant{n}@bipsu.edu.ph',
            'password': 'a-long-enough-password',
            'first_name': 'A', 'last_name': 'B',
            'student_id': f'2022-{n:05d}', 'course': 'BSCS',
            'year_level': 2, 'gwa': 1.75,
        }, content_type='application/json')

    def test_the_sixth_submission_from_one_caller_is_refused(self):
        for n in range(5):
            self.assertEqual(
                self._submit(n).status_code, 201,
                'the fixture stopped being a valid registration')
        self.assertEqual(
            self._submit(99).status_code, 429,
            'five successful registrations bought the caller a sixth')

    def test_the_refusal_explains_the_wait(self):
        for n in range(5):
            self._submit(n)
        self.assertIn('Too many registrations',
                      self._submit(99).json().get('detail', ''))

    def test_submissions_at_the_form_lock_the_endpoint(self):
        for n in range(5):
            self.c.post('/register/', {
                'account_type': 'student',
                'email': f'walkin{n}@bipsu.edu.ph',
                'first_name': 'A', 'last_name': 'B'})
        self.assertEqual(
            self._submit(99).status_code, 429,
            'the endpoint handed out a fresh allowance the form had spent')
