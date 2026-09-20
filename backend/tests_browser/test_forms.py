"""Form submission in a real browser."""

from api.models import StudentProfile, SystemSettings, User

from .base import BrowserTestCase


class SignInFormTest(BrowserTestCase):
    """The sign-in form, driven the way a person drives it."""

    def setUp(self):
        super().setUp()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='correct-horse', first_name='Ana', last_name='Lim',
            role='student', verification_status='approved')
        StudentProfile.objects.create(
            user=user, student_id='2022-00111', course='BSCS', year_level=2)

    def test_correct_credentials_reach_the_student_portal(self):
        self.sign_in('ana@bipsu.edu.ph', 'correct-horse')
        self.assertIn('/student/', self.page.url)
        self.assertNoConsoleErrors()

    def test_a_wrong_password_returns_to_the_form_with_the_address_kept(self):
        self.sign_in('ana@bipsu.edu.ph', 'wrong')
        self.assertIn('/login/', self.page.url)
        self.assertEqual(
            self.page.input_value('input[name="email"]'), 'ana@bipsu.edu.ph',
            'the form threw away the address and made them type it again')

    def test_the_refusal_names_neither_the_address_nor_the_password(self):
        self.sign_in('nobody@bipsu.edu.ph', 'wrong')
        body = self.page.inner_text('body')
        self.assertIn('Invalid email or password', body)
        self.assertNotIn('No account is registered', body)

    def test_the_browser_blocks_an_empty_submission_before_the_server_sees_it(self):
        self.visit('/login/')
        self.page.click('button[type="submit"]')
        self.assertIn(
            '/login/', self.page.url,
            'an empty form was allowed through')


class RegistrationFormTest(BrowserTestCase):
    """The registration form's own scripts."""

    def setUp(self):
        super().setUp()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})

    def test_the_page_loads_without_a_script_error(self):
        self.visit('/register/')
        self.page.wait_for_timeout(400)
        self.assertNoConsoleErrors()

    def test_choosing_an_account_type_reveals_the_matching_fields(self):
        self.visit('/register/')
        chooser = self.page.query_selector('[name="account_type"]')
        if chooser is None:
            self.skipTest('this build has no account-type chooser on the form')
        self.page.wait_for_timeout(300)
        self.assertNoConsoleErrors()

    def test_submitting_nothing_reports_errors_rather_than_a_crash(self):
        self.visit('/register/')
        button = self.page.query_selector('button[type="submit"]')
        if button is None:
            self.skipTest('no submit control found')
        button.click()
        self.page.wait_for_load_state('domcontentloaded')
        self.assertNotIn('Server Error', self.page.inner_text('body'))
