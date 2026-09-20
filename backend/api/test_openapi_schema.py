"""The published API contract, checked against the API itself.

A schema is only a contract if it is complete and true. These cases assert
that every routed ``/api/`` endpoint appears in it, that none of them is
documented as an untyped blob, and that the response shapes named in
``api/api_schema.py`` match what the views actually return.
"""

from rest_framework.authtoken.models import Token

from django.test import Client, TestCase
from django.urls import get_resolver

from api.models import (
    AcademicRenewal, Application, Scholarship, StudentProfile, SystemSettings,
    User,
)

NOT_IN_THE_SCHEMA = ('api/schema/', 'api/docs/', 'api/redoc/')


def routed_api_paths():
    """Every ``/api/`` route in the URL map, as the schema would name it."""
    found = []
    for pattern in get_resolver().url_patterns:
        route = str(getattr(pattern, 'pattern', ''))
        if not route.startswith('api/') or route in NOT_IN_THE_SCHEMA:
            continue
        found.append('/' + route)
    return found


def generated_schema():
    """The OpenAPI document drf-spectacular would publish."""
    from drf_spectacular.generators import SchemaGenerator

    return SchemaGenerator().get_schema(request=None, public=True)


class SchemaCoverageTest(TestCase):

    def setUp(self):
        self.schema = generated_schema()

    def test_every_routed_api_endpoint_is_in_the_published_schema(self):
        documented = set(self.schema['paths'])
        for route in routed_api_paths():
            wanted = route.replace('<int:pk>', '{id}').replace('<str:type>', '{type}')
            with self.subTest(route=route):
                self.assertIn(wanted, documented)

    def test_the_schema_names_the_system_rather_than_a_framework_default(self):
        self.assertEqual(self.schema['info']['title'], 'BiPSU SRMS API')
        self.assertTrue(self.schema['info']['version'])

    def test_no_endpoint_is_documented_as_an_unspecified_blob(self):
        for path, operations in self.schema['paths'].items():
            for method, operation in operations.items():
                ok = operation.get('responses', {}).get('200') or {}
                schema = (ok.get('content', {})
                          .get('application/json', {}).get('schema'))
                if schema is None:
                    continue
                with self.subTest(path=path, method=method):
                    self.assertNotEqual(
                        schema, {'type': 'object', 'additionalProperties': {}},
                        'this endpoint publishes no response shape at all')

    def test_the_hand_written_views_carry_a_response_shape(self):
        by_hand = {
            '/api/auth/register/': 'post',
            '/api/auth/login/': 'post',
            '/api/student/dashboard/': 'get',
            '/api/vpsea/dashboard/': 'get',
            '/api/vpsea/analytics/': 'get',
            '/api/vpsea/reports/': 'get',
            '/api/vpsea/ranking/': 'get',
            '/api/vpsea/archives/{type}/upload/': 'post',
        }
        for path, method in by_hand.items():
            with self.subTest(path=path):
                operation = self.schema['paths'][path][method]
                codes = set(operation['responses'])
                self.assertTrue(codes & {'200', '201'})

    def test_the_schema_endpoint_is_served_and_parses(self):
        officer = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea')
        key, _ = Token.objects.get_or_create(user=officer)
        client = Client(HTTP_AUTHORIZATION=f'Token {key.key}')

        response = client.get('/api/schema/')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.content), 1000)

    def test_the_schema_is_not_public(self):
        response = Client().get('/api/schema/')
        self.assertIn(response.status_code, (401, 403))


class SchemaTruthfulnessTest(TestCase):
    """The documented shape and the real response, compared field by field."""

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.officer = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea')
        student = User.objects.create_user(
            username='2026-0001@bipsu.edu.ph', email='2026-0001@bipsu.edu.ph',
            password='pw', first_name='Maria', last_name='Santos', role='student')
        self.profile = StudentProfile.objects.create(
            user=student, student_id='2026-0001', course='BSCS', year_level=2)
        scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        Application.objects.create(
            student=self.profile, scholarship=scholarship, status='Approved',
            term_label='26-1')
        AcademicRenewal.objects.create(student=self.profile, status='Pending')

        self.office = self._client(self.officer)
        self.student = self._client(student)

    def _client(self, user):
        """A token-authenticated client for one account."""
        key, _ = Token.objects.get_or_create(user=user)
        return Client(HTTP_AUTHORIZATION=f'Token {key.key}')

    def _assert_matches(self, serializer_class, payload):
        """The payload carries exactly the documented keys, no more, no fewer."""
        documented = set(serializer_class().fields)
        self.assertEqual(
            set(payload), documented,
            f'{serializer_class.__name__} and the real response have drifted')

    def test_the_office_dashboard_returns_what_the_schema_promises(self):
        from api import api_schema

        response = self.office.get('/api/vpsea/dashboard/')
        self.assertEqual(response.status_code, 200)
        self._assert_matches(api_schema.OfficeDashboardSerializer,
                             response.json())

    def test_the_student_dashboard_returns_what_the_schema_promises(self):
        from api import api_schema

        response = self.student.get('/api/student/dashboard/')
        self.assertEqual(response.status_code, 200)
        self._assert_matches(api_schema.StudentDashboardSerializer,
                             response.json())

    def test_the_analytics_endpoint_returns_what_the_schema_promises(self):
        from api import api_schema

        response = self.office.get('/api/vpsea/analytics/')
        self.assertEqual(response.status_code, 200)
        self._assert_matches(api_schema.OfficeAnalyticsSerializer,
                             response.json())

    def test_the_ranking_endpoint_returns_what_the_schema_promises(self):
        from api import api_schema

        response = self.office.get('/api/vpsea/ranking/')
        self.assertEqual(response.status_code, 200)
        self._assert_matches(api_schema.AffirmativeRankingSerializer,
                             response.json())

    def test_the_reports_endpoint_returns_what_the_schema_promises(self):
        from api import api_schema

        response = self.office.get('/api/vpsea/reports/')
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertTrue(rows)
        self._assert_matches(api_schema.ReportLinkSerializer, rows[0])

    def test_a_token_is_issued_in_the_documented_shape(self):
        from api import api_schema

        response = Client().post('/api/auth/login/', {
            'email': 'vpsea@bipsu.edu.ph', 'password': 'pw'})
        self.assertEqual(response.status_code, 200)
        self._assert_matches(api_schema.TokenSerializer, response.json())
