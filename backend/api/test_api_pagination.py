from django.test import Client, TestCase
from rest_framework.authtoken.models import Token

from api.models import (
    Announcement, Application, Scholarship, StudentProfile, SystemSettings,
    User,
)
from api.pagination import SRMSPagination

PAGE_SIZE = SRMSPagination.page_size


def _token_client(user):
    token, _ = Token.objects.get_or_create(user=user)
    return Client(HTTP_AUTHORIZATION=f'Token {token.key}')


class ListEndpointsArePagedTest(TestCase):
    """No list endpoint may return its whole table.

    Raised by the evaluators alongside the long office tables. An unbounded
    list response grows with the database and has to be serialised entirely
    into the 512 MB container before a single byte is sent.
    """

    ROWS = PAGE_SIZE * 2 + 5

    @classmethod
    def setUpTestData(cls):
        """One application per scholarship.

        A student may hold only one award per scholarship per term, so the
        rows have to differ by programme rather than repeat.
        """
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        cls.student = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student',
            verification_status='approved')
        cls.profile = StudentProfile.objects.create(
            user=cls.student, student_id='2022-00111', course='BSCS',
            year_level=2)
        scholarships = Scholarship.objects.bulk_create([
            Scholarship(name=f'Programme {n:03d}', type='Academic',
                        category='application', description='x',
                        eligibility='x', requirements=[])
            for n in range(cls.ROWS)
        ])
        Application.objects.bulk_create([
            Application(student=cls.profile, scholarship=scholarship,
                        status='Approved', term_label='26-1',
                        school_year='2026-2027', semester='1st Semester')
            for scholarship in scholarships
        ])
        Announcement.objects.bulk_create([
            Announcement(title=f'Notice {n}', body='x')
            for n in range(cls.ROWS)
        ])

    def setUp(self):
        self.c = _token_client(self.student)

    def test_a_list_response_is_an_envelope_not_a_bare_array(self):
        body = self.c.get('/api/student/applications/').json()
        self.assertIsInstance(
            body, dict,
            'the endpoint still returns a bare array, so nothing is paged')
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, body)

    def test_one_page_holds_no_more_than_the_page_size(self):
        body = self.c.get('/api/student/applications/').json()
        self.assertEqual(len(body['results']), PAGE_SIZE)
        self.assertEqual(body['count'], self.ROWS)

    def test_the_pages_together_hold_everything(self):
        seen, url = 0, '/api/student/applications/'
        while url:
            body = self.c.get(url).json()
            seen += len(body['results'])
            url = body['next']
        self.assertEqual(
            seen, self.ROWS,
            'walking every page did not reach every row')

    def test_a_caller_may_widen_the_page(self):
        body = self.c.get('/api/student/applications/?page_size=100').json()
        self.assertEqual(len(body['results']), 100)

    def test_a_caller_may_not_widen_it_past_the_ceiling(self):
        body = self.c.get('/api/student/applications/?page_size=100000').json()
        self.assertLessEqual(
            len(body['results']), SRMSPagination.max_page_size,
            'a caller could ask for the whole table and get it')

    def test_announcements_are_paged_too(self):
        body = self.c.get('/api/student/announcements/').json()
        self.assertEqual(len(body['results']), PAGE_SIZE)

    def test_a_page_past_the_end_is_a_404_rather_than_a_crash(self):
        self.assertEqual(
            self.c.get('/api/student/applications/?page=9999').status_code, 404)


class OfficeListEndpointsArePagedTest(TestCase):
    """The office endpoints read the largest tables, so they matter most."""

    ROWS = PAGE_SIZE + 10

    @classmethod
    def setUpTestData(cls):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic',
            category='application', description='x', eligibility='x',
            requirements=[])
        for n in range(cls.ROWS):
            user = User.objects.create_user(
                username=f's{n:03d}@bipsu.edu.ph', email=f's{n:03d}@bipsu.edu.ph',
                password='pw', first_name=f'S{n}', last_name='T',
                role='student')
            profile = StudentProfile.objects.create(
                user=user, student_id=f'2024-{n:05d}', course='BSCS',
                year_level=1)
            Application.objects.create(
                student=profile, scholarship=scholarship, status='Approved',
                term_label='26-1', school_year='2026-2027',
                semester='1st Semester')
        cls.officer = User.objects.create_user(
            username='office@bipsu.edu.ph', email='office@bipsu.edu.ph',
            password='pw', first_name='R', last_name='B', role='vpsea')

    def setUp(self):
        self.c = _token_client(self.officer)

    def test_the_office_application_list_is_paged(self):
        body = self.c.get('/api/vpsea/applications/').json()
        self.assertEqual(len(body['results']), PAGE_SIZE)
        self.assertEqual(body['count'], self.ROWS)

    def test_the_ranking_keeps_its_summary_while_paging_the_rows(self):
        """The ranking is an envelope, so it pages differently and on purpose."""
        body = self.c.get('/api/vpsea/ranking/?limit=5').json()
        self.assertLessEqual(len(body['recommendations']), 5)
        self.assertIn('recommendation_count', body)
        for key in ('eligible_count', 'ineligible_count',
                    'in_target_group_count', 'passing_threshold'):
            self.assertIn(
                key, body,
                f'paging the ranking dropped {key} from the summary')

    def test_the_ranking_window_is_capped(self):
        body = self.c.get('/api/vpsea/ranking/?limit=999999').json()
        self.assertLessEqual(
            len(body['recommendations']),
            max(1, body['recommendation_count']))
        self.assertLessEqual(body['limit'], 200)

    def test_nonsense_ranking_paging_falls_back_rather_than_erroring(self):
        r = self.c.get('/api/vpsea/ranking/?limit=banana&offset=nope')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['offset'], 0)
