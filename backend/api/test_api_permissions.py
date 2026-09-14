from rest_framework.authtoken.models import Token

from django.test import Client, TestCase

from api.models import (
    AcademicRenewal, Application, Scholarship, StudentProfile, User,
)


OFFICE_ROUTES = [
    ('get',   '/api/vpsea/dashboard/'),
    ('get',   '/api/vpsea/applications/'),
    ('get',   '/api/vpsea/renewals/'),
    ('get',   '/api/vpsea/archives/Academic/'),
    ('get',   '/api/vpsea/analytics/'),
    ('get',   '/api/vpsea/announcements/'),
    ('get',   '/api/vpsea/reports/'),
    ('get',   '/api/vpsea/ranking/'),
]


def token_client(user):
    key, _ = Token.objects.get_or_create(user=user)
    return Client(HTTP_AUTHORIZATION=f'Token {key.key}')


class OfficeEndpointsTest(TestCase):

    def setUp(self):
        self.officer = User.objects.create_user(
            username='officer@bipsu.edu.ph', email='officer@bipsu.edu.ph',
            password='pw', first_name='Ofelia', last_name='Officer', role='vpsea')

        self.outsider = User.objects.create_user(
            username='juan@bipsu.edu.ph', email='juan@bipsu.edu.ph',
            password='pw', first_name='Juan', last_name='Dela Cruz', role='student')
        self.profile = StudentProfile.objects.create(
            user=self.outsider, student_id='2026-0001', course='BSIT')

        self.scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        self.application = Application.objects.create(
            student=self.profile, scholarship=self.scholarship,
            status='Pending Validation')

    def test_a_students_token_reaches_no_office_endpoint(self):
        client = token_client(self.outsider)
        for method, url in OFFICE_ROUTES:
            with self.subTest(url=url):
                response = getattr(client, method)(url)
                self.assertEqual(
                    response.status_code, 403,
                    f'{url} answered {response.status_code} to a student token')

    def test_a_student_cannot_approve_their_own_application(self):
        response = token_client(self.outsider).patch(
            f'/api/vpsea/applications/{self.application.pk}/',
            {'status': 'Approved'}, content_type='application/json')

        self.assertEqual(response.status_code, 403)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'Pending Validation')

    def test_a_student_cannot_publish_an_announcement(self):
        response = token_client(self.outsider).post(
            '/api/vpsea/announcements/',
            {'title': 'Free money', 'body': 'Call this number'},
            content_type='application/json')

        self.assertEqual(response.status_code, 403)

    def test_a_staff_token_reaches_no_office_endpoint_either(self):
        employee = User.objects.create_user(
            username='emp@bipsu.edu.ph', email='emp@bipsu.edu.ph', password='pw',
            first_name='Emma', last_name='Ployee', role='nsu_staff')
        client = token_client(employee)
        for _method, url in OFFICE_ROUTES:
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 403)

    def test_an_anonymous_caller_is_refused(self):
        for _method, url in OFFICE_ROUTES:
            with self.subTest(url=url):
                self.assertEqual(Client().get(url).status_code, 401)

    def test_an_officer_still_reaches_every_one_of_them(self):
        client = token_client(self.officer)
        for method, url in OFFICE_ROUTES:
            with self.subTest(url=url):
                response = getattr(client, method)(url)
                self.assertEqual(
                    response.status_code, 200,
                    f'{url} answered {response.status_code} to an officer')

    def test_an_officer_can_still_decide_an_application(self):
        response = token_client(self.officer).patch(
            f'/api/vpsea/applications/{self.application.pk}/',
            {'status': 'Approved'}, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'Approved')

    def test_a_superuser_reaches_them_whatever_role_it_carries(self):
        root = User.objects.create_superuser(
            username='root@bipsu.edu.ph', email='root@bipsu.edu.ph', password='pw')
        self.assertEqual(
            token_client(root).get('/api/vpsea/dashboard/').status_code, 200)

    def test_a_student_still_reads_their_own_records(self):
        AcademicRenewal.objects.filter(student=self.profile).delete()
        client = token_client(self.outsider)
        for url in ('/api/student/profile/', '/api/student/applications/',
                    '/api/student/notifications/', '/api/student/announcements/',
                    '/api/student/scholarships/', '/api/student/dashboard/'):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200)
