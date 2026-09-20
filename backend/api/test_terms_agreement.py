from django.test import Client, TestCase

from api import terms
from api.models import StudentProfile, SystemSettings, User
from api.fixtures_registration import a_staff_member, a_student


def without_consent(payload):
    return {name: value for name, value in payload.items()
            if name != 'accept_terms'}


class TheFormRefusesARegistrationThatDidNotAgreeTest(TestCase):
    def setUp(self):
        self.c = Client()

    def test_a_student_who_did_not_tick_the_box_is_turned_back(self):
        r = self.c.post('/register/', without_consent(a_student()))
        self.assertContains(r, 'Terms of Use and Data Privacy Notice')
        self.assertFalse(User.objects.filter(email='juan@bipsu.edu.ph').exists())

    def test_the_reason_says_what_to_do_about_it(self):
        r = self.c.post('/register/', without_consent(a_student()))
        self.assertContains(r, 'read and accept')

    def test_a_staff_member_who_did_not_tick_it_is_turned_back_too(self):
        r = self.c.post('/register/', without_consent(a_staff_member()))
        self.assertContains(r, 'read and accept')
        self.assertFalse(User.objects.filter(email='ernesto@bipsu.edu.ph').exists())

    def test_nothing_of_the_registration_survives_the_refusal(self):
        self.c.post('/register/', without_consent(a_student()))
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(StudentProfile.objects.count(), 0)

    def test_what_they_typed_comes_back_so_the_form_is_not_retyped(self):
        r = self.c.post('/register/', without_consent(a_student()))
        self.assertContains(r, 'juan@bipsu.edu.ph')
        self.assertContains(r, '2022-00999')


class AgreementIsRecordedOnTheAccountTest(TestCase):

    def setUp(self):
        self.c = Client()

    def test_a_student_registration_records_the_version_and_the_moment(self):
        self.c.post('/register/', a_student())
        user = User.objects.get(email='juan@bipsu.edu.ph')
        self.assertEqual(user.terms_version, terms.VERSION)
        self.assertIsNotNone(user.terms_accepted_at)
        self.assertTrue(user.accepted_terms)

    def test_a_staff_registration_records_it_the_same_way(self):
        self.c.post('/register/', a_staff_member())
        user = User.objects.get(email='ernesto@bipsu.edu.ph')
        self.assertEqual(user.terms_version, terms.VERSION)
        self.assertTrue(user.accepted_terms)

    def test_an_account_the_office_created_is_not_recorded_as_having_agreed(self):
        office = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph', password='pw',
            first_name='Rosario', last_name='Bayhon', role='vpsea')
        self.assertEqual(office.terms_version, '')
        self.assertIsNone(office.terms_accepted_at)
        self.assertFalse(office.accepted_terms)

    def test_half_a_record_is_not_a_record(self):
        user = User(email='x@bipsu.edu.ph', terms_version=terms.VERSION)
        self.assertFalse(user.accepted_terms)


class ANoticeRevisedMidFormIsNoticedTest(TestCase):
    def setUp(self):
        self.c = Client()

    def test_a_stale_version_sends_the_form_back(self):
        r = self.c.post('/register/', a_student(terms_version='0.9'))
        self.assertContains(r, 'was updated while you were filling this form in')
        self.assertFalse(User.objects.filter(email='juan@bipsu.edu.ph').exists())

    def test_the_current_version_goes_through(self):
        self.c.post('/register/', a_student(terms_version=terms.VERSION))
        self.assertTrue(User.objects.filter(email='juan@bipsu.edu.ph').exists())

    def test_a_caller_that_posts_no_version_is_not_accused_of_a_stale_one(self):
        payload = {name: value for name, value in a_student().items()
                   if name != 'terms_version'}
        self.c.post('/register/', payload)
        self.assertTrue(User.objects.filter(email='juan@bipsu.edu.ph').exists())


class TheApiDoorRecordsConsentWhenItIsGivenTest(TestCase):
    PAYLOAD = {
        'email': 'api@bipsu.edu.ph', 'password': 'demo1234',
        'first_name': 'Api', 'last_name': 'Caller',
        'student_id': '2022-00555', 'course': 'BSCS', 'year_level': 2, 'gwa': 1.75,
    }

    def setUp(self):
        self.c = Client()

    def test_a_caller_that_agrees_has_it_recorded(self):
        r = self.c.post('/api/auth/register/',
                        dict(self.PAYLOAD, accept_terms=True),
                        content_type='application/json')
        self.assertEqual(r.status_code, 201)
        user = User.objects.get(email='api@bipsu.edu.ph')
        self.assertEqual(user.terms_version, terms.VERSION)
        self.assertTrue(user.accepted_terms)

    def test_a_caller_that_does_not_is_left_blank_rather_than_assumed(self):
        r = self.c.post('/api/auth/register/', self.PAYLOAD,
                        content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertFalse(User.objects.get(email='api@bipsu.edu.ph').accepted_terms)


class TheNoticeIsOnTheFormToReadTest(TestCase):
    def setUp(self):
        SystemSettings.objects.get_or_create(pk=1)
        self.html = Client().get('/register/').content.decode()

    def test_the_sentence_beside_the_box_is_the_one_from_the_module(self):
        self.assertIn('Data Privacy Act of 2012', self.html)
        self.assertIn('consent to the', self.html)

    def test_every_section_of_the_notice_is_on_the_page(self):
        missing = [section['heading'] for section in terms.SECTIONS
                   if section['heading'] not in self.html]
        self.assertEqual(missing, [], f'Not rendered onto /register/: {missing}')

    def test_the_version_on_the_form_is_the_version_that_gets_recorded(self):
        self.assertIn(f'value="{terms.VERSION}"', self.html)

    def test_the_box_is_asked_for_in_the_browser_as_well(self):
        self.assertIn('name="accept_terms"', self.html)
        box = self.html[self.html.index('name="accept_terms"'):]
        self.assertIn('required', box[:200])


class TheOfficeCanReadTheConsentBackTest(TestCase):
    def setUp(self):
        SystemSettings.objects.get_or_create(pk=1)
        User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph', password='pw',
            first_name='Rosario', last_name='Bayhon', role='vpsea')
        self.c = Client()
        self.c.post('/register/', a_student())
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))

    def test_the_account_record_names_the_version_and_the_date(self):
        html = self.c.get('/vpsea/accounts/').content.decode()
        self.assertIn('Terms &amp; Data Privacy', html)
        self.assertIn(f'Accepted version {terms.VERSION}', html)

    def test_an_account_that_was_never_asked_says_so_rather_than_nothing(self):
        never_asked = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student',
            verification_status='pending')
        StudentProfile.objects.create(
            user=never_asked, student_id='2022-00111', course='BSCS', year_level=2)
        html = self.c.get('/vpsea/accounts/').content.decode()
        self.assertIn('Not recorded', html)


class TheNoticeItselfTest(TestCase):
    def test_every_section_has_a_heading_and_something_under_it(self):
        for section in terms.SECTIONS:
            self.assertTrue(section['heading'].strip(), section)
            self.assertTrue(section['body'], section['heading'])
            for paragraph in section['body']:
                self.assertTrue(paragraph.strip(), section['heading'])

    def test_the_notice_covers_what_the_data_privacy_act_asks_it_to(self):
        text = ' '.join(paragraph
                        for section in terms.SECTIONS
                        for paragraph in section['body']).casefold()
        for required in ('data privacy act', 'national privacy commission',
                         'right', 'kept', 'shared'):
            self.assertIn(required, text)

    def test_there_is_a_version_to_record(self):
        self.assertTrue(terms.VERSION.strip())
