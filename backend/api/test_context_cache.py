from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from api.models import StudentProfile, SystemSettings, User

REAL_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'context-cache-tests',
    },
}


@override_settings(CACHES=REAL_CACHE)
class ActiveTermCacheTest(TestCase):
    """The active term is read on every page, and changes a few times a year.

    Settings pin the test cache to a dummy backend that forgets everything, so
    these cases supply a real one — against the dummy the assertions would
    pass whether or not anything was cached.
    """

    def setUp(self):
        cache.clear()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student',
            verification_status='approved')
        StudentProfile.objects.create(
            user=user, student_id='2022-00111', course='BSCS', year_level=2)
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def _queries(self, path='/student/applications/'):
        with CaptureQueriesContext(connection) as captured:
            self.c.get(path)
        return [q['sql'] for q in captured.captured_queries]

    def test_the_second_page_view_re_reads_less_than_the_first(self):
        first = len(self._queries())
        second = len(self._queries())
        self.assertLess(
            second, first,
            f'the second render cost the same {first} queries as the first, '
            'so nothing was cached')

    def test_the_term_costs_no_query_once_it_has_been_read(self):
        """Asserted on the helper, not the page.

        A page may read ``SystemSettings`` again for its own reasons — the
        application window, the term label on a form. What must not happen is
        the *context processor* reading it on every render of every page.
        """
        from api.context_processors import _active_term
        _active_term()
        with self.assertNumQueries(0):
            _active_term()

    def test_the_page_stops_re_reading_the_term_after_the_first_render(self):
        first = [q for q in self._queries() if 'systemsettings' in q.lower()]
        second = [q for q in self._queries() if 'systemsettings' in q.lower()]
        self.assertLess(
            len(second), len(first),
            f'the term was read {len(first)} times on the first render and '
            f'{len(second)} on the second — the cache saved nothing')

    def test_rolling_the_term_is_visible_at_once_rather_than_after_a_wait(self):
        self.c.get('/student/applications/')
        settings_obj = SystemSettings.objects.get(pk=1)
        settings_obj.academic_year = '26-2'
        settings_obj.save()

        from api.context_processors import _active_term
        self.assertEqual(
            _active_term()['active_semester'], '2nd Semester',
            'the cached term survived a rollover, so the whole site would '
            'show the wrong semester until the entry expired')

    def test_a_missing_settings_row_does_not_break_the_page(self):
        cache.clear()
        SystemSettings.objects.all().delete()
        self.assertEqual(self.c.get('/student/applications/').status_code, 200)


@override_settings(CACHES=REAL_CACHE)
class PendingBadgeCacheTest(TestCase):
    """The office badge counts two tables; it does not need to be exact."""

    def setUp(self):
        cache.clear()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        User.objects.create_user(
            username='office@bipsu.edu.ph', email='office@bipsu.edu.ph',
            password='pw', first_name='R', last_name='B', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='office@bipsu.edu.ph', password='pw'))

    def test_the_badge_is_counted_once_and_then_reused(self):
        first = self.c.get('/vpsea/').context['pending_accounts']
        User.objects.create_user(
            username='new@bipsu.edu.ph', email='new@bipsu.edu.ph',
            password='pw', first_name='N', last_name='B', role='student',
            verification_status='pending')
        self.assertEqual(
            self.c.get('/vpsea/').context['pending_accounts'], first,
            'the badge was recounted immediately, so it is not cached at all')

    def test_the_real_count_is_still_correct_once_the_entry_expires(self):
        self.c.get('/vpsea/')
        cache.delete('ctx:pending-accounts')
        User.objects.create_user(
            username='new@bipsu.edu.ph', email='new@bipsu.edu.ph',
            password='pw', first_name='N', last_name='B', role='student',
            verification_status='pending')
        self.assertEqual(self.c.get('/vpsea/').context['pending_accounts'], 1)
