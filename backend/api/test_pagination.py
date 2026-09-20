from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from api.models import StudentProfile, SystemSettings, User
from api.views_shared import DEFAULT_PAGE_SIZE


def _pending(n):
    user = User.objects.create_user(
        username=f'applicant{n:03d}@bipsu.edu.ph',
        email=f'applicant{n:03d}@bipsu.edu.ph', password='pw',
        first_name=f'Applicant{n:03d}', last_name=f'Family{n:03d}',
        role='student', verification_status='pending')
    StudentProfile.objects.create(
        user=user, student_id=f'2024-{n:05d}', course='BSCS',
        year_level=(n % 4) + 1)
    return user


class AccountQueuePaginationTest(TestCase):
    """The verification queue must not load every pending account at once.

    Raised by the evaluators: the page fetched the whole table and then issued
    further queries for each row's declarations, which is fine at a demo's
    handful of registrations and is not at a few years of intake.
    """

    PENDING = DEFAULT_PAGE_SIZE * 3

    @classmethod
    def setUpTestData(cls):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        for n in range(cls.PENDING):
            _pending(n)
        User.objects.create_user(
            username='office@bipsu.edu.ph', email='office@bipsu.edu.ph',
            password='pw', first_name='R', last_name='B', role='vpsea')

    def setUp(self):
        self.c = Client()
        self.assertTrue(self.c.login(email='office@bipsu.edu.ph', password='pw'))

    def test_one_page_holds_no_more_than_the_page_size(self):
        page = self.c.get('/vpsea/accounts/').context['pending_page']['page']
        self.assertEqual(len(page.object_list), DEFAULT_PAGE_SIZE)
        self.assertEqual(page.paginator.count, self.PENDING)

    def test_the_later_pages_hold_the_rest(self):
        seen = set()
        for number in (1, 2, 3):
            page = self.c.get(
                f'/vpsea/accounts/?pending_page={number}'
            ).context['pending_page']['page']
            seen.update(account.email for account in page.object_list)
        self.assertEqual(
            len(seen), self.PENDING,
            'paging through every page did not reach every pending account')

    def test_a_page_beyond_the_end_gives_the_last_page_not_an_error(self):
        r = self.c.get('/vpsea/accounts/?pending_page=999')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['pending_page']['page'].number,
                         r.context['pending_page']['page'].paginator.num_pages)

    def test_a_nonsense_page_number_is_not_a_crash(self):
        self.assertEqual(
            self.c.get('/vpsea/accounts/?pending_page=banana').status_code, 200)

    def test_the_query_count_does_not_grow_with_the_queue(self):
        with CaptureQueriesContext(connection) as first:
            self.c.get('/vpsea/accounts/')
        before = len(first.captured_queries)

        for n in range(self.PENDING, self.PENDING * 2):
            _pending(n)

        with CaptureQueriesContext(connection) as second:
            self.c.get('/vpsea/accounts/')
        after = len(second.captured_queries)

        self.assertLessEqual(
            after, before + 2,
            f'doubling the queue took the page from {before} to {after} '
            'queries — it is still reading the whole table')

    def test_the_two_queues_page_independently(self):
        r = self.c.get('/vpsea/accounts/?pending_page=2')
        self.assertEqual(r.context['pending_page']['page'].number, 2)
        self.assertEqual(
            r.context['decided_page']['page'].number, 1,
            'paging the pending queue moved the decided one as well')

    def test_paging_keeps_the_rest_of_the_query_string(self):
        r = self.c.get('/vpsea/accounts/?tab=staff&pending_page=2')
        self.assertIn(
            'tab=staff', r.context['pending_page']['querystring'],
            'the page links drop the current tab, so paging resets the view')
