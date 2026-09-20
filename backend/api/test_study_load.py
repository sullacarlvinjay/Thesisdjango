from django.test import Client, TestCase

from api.models import StudentProfile, SystemSettings, User
from api.test_registration_payload import CERTIFICATES, a_student


class StudyLoadIsRequiredTest(TestCase):
    """Registration must collect proof the applicant is actually enrolled.

    Asked for by the office: a student number is self-reported and survives
    the student leaving, so on its own it does not establish that whoever is
    registering is currently a bonafide student. The registrar's certificate
    of registration does.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        self.c = Client()

    def test_it_is_one_of_the_certificates_the_form_demands(self):
        self.assertIn('study_load', CERTIFICATES)

    def test_the_form_asks_for_it(self):
        html = self.c.get('/register/').content.decode()
        self.assertIn('name="study_load"', html)
        self.assertIn('Study Load', html)

    def test_registering_without_it_is_refused(self):
        payload = a_student(email='ana@bipsu.edu.ph', student_id='2022-00901')
        payload.pop('study_load')
        r = self.c.post('/register/', payload)
        self.assertContains(r, 'Certificate of Registration')
        self.assertFalse(
            User.objects.filter(email='ana@bipsu.edu.ph').exists(),
            'an account was created without proof of enrolment')

    def test_registering_with_it_stores_the_document(self):
        self.c.post('/register/', a_student(
            email='ben@bipsu.edu.ph', student_id='2022-00902'))
        profile = StudentProfile.objects.get(student_id='2022-00902')
        self.assertTrue(
            profile.study_load,
            'the certificate was accepted but not kept, so the office has '
            'nothing to check')

    def test_a_disallowed_file_type_is_refused(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        payload = a_student(email='ivy@bipsu.edu.ph', student_id='2022-00903')
        payload['study_load'] = SimpleUploadedFile(
            'load.exe', b'MZ', content_type='application/octet-stream')
        r = self.c.post('/register/', payload)
        self.assertContains(r, 'Unsupported file type')
        self.assertFalse(User.objects.filter(email='ivy@bipsu.edu.ph').exists())


class StudyLoadReachesTheOfficeTest(TestCase):
    """Collecting it is only useful if the reviewer can open it."""

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        User.objects.create_user(
            username='office@bipsu.edu.ph', email='office@bipsu.edu.ph',
            password='pw', first_name='R', last_name='B', role='vpsea')
        Client().post('/register/', a_student(
            email='ana@bipsu.edu.ph', student_id='2022-00911'))
        self.c = Client()
        self.assertTrue(self.c.login(email='office@bipsu.edu.ph', password='pw'))

    def test_the_verification_queue_offers_it_for_review(self):
        html = self.c.get('/vpsea/accounts/').content.decode()
        self.assertIn('Study Load', html)
        self.assertIn('profile/study_load/', html)

    def test_a_record_without_one_says_so_rather_than_showing_a_dash(self):
        profile = StudentProfile.objects.get(student_id='2022-00911')
        profile.study_load = None
        profile.save()
        self.assertContains(self.c.get('/vpsea/accounts/'), 'Not submitted')


class StudyLoadIsNotPublicTest(TestCase):
    """It is a student document, so it is owner-gated like the others."""

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        Client().post('/register/', a_student(
            email='ana@bipsu.edu.ph', student_id='2022-00921'))
        self.profile = StudentProfile.objects.get(student_id='2022-00921')

    def test_a_stranger_cannot_fetch_it(self):
        other = User.objects.create_user(
            username='ben@bipsu.edu.ph', email='ben@bipsu.edu.ph',
            password='pw', first_name='Ben', last_name='Cruz', role='student')
        StudentProfile.objects.create(
            user=other, student_id='2022-00922', course='BSCS', year_level=1)
        c = Client()
        self.assertTrue(c.login(email='ben@bipsu.edu.ph', password='pw'))
        self.assertEqual(
            c.get(self.profile.study_load.url).status_code, 404,
            "another student could read someone else's enrolment document")

    def test_a_signed_out_visitor_cannot_fetch_it(self):
        self.assertEqual(
            Client().get(self.profile.study_load.url).status_code, 404)

    def test_the_owner_can_fetch_it(self):
        """A fresh registration is unverified, so the account is approved first.

        Without that the case would pass for the wrong reason: a signed-out
        visitor is refused too, and the point here is that the owner is not.
        """
        owner = User.objects.get(email='ana@bipsu.edu.ph')
        owner.decide_verification('approved', '', None)
        c = Client()
        self.assertTrue(c.login(email='ana@bipsu.edu.ph', password='demo1234'))
        self.assertEqual(c.get(self.profile.study_load.url).status_code, 200)

