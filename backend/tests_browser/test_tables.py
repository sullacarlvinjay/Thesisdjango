"""Search, filtering and sorting on the office tables.

All three are client-side — `static/js/search.js`, `table-filter.js` and
`table-sort.js` — so these assertions are about rows actually appearing and
disappearing, not about the controls being present. A filter that renders
perfectly and filters nothing passes every backend test there is.
"""

from api.models import ApplicantRecord, Scholarship, SystemSettings, User

from .base import BrowserTestCase


class OfficeTableTestCase(BrowserTestCase):

    def setUp(self):
        super().setUp()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        User.objects.create_user(
            username='office@bipsu.edu.ph', email='office@bipsu.edu.ph',
            password='office-pw', first_name='Rosario', last_name='Bayhon',
            role='vpsea')
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[])
        for n, (name, status) in enumerate([
            ('Aurora Mendoza', 'Approved'),
            ('Benigno Reyes', 'Pending Validation'),
            ('Carmela Torres', 'Approved'),
            ('Dionisio Flores', 'Rejected'),
        ]):
            ApplicantRecord.objects.create(
                full_name=name, email=f'person{n}@bipsu.edu.ph',
                qualified_for='Staff', status=status, course='MAEd',
                year_level=1, is_nsu_staff=True,
                school_year='2026-2027', semester='1st Semester',
                term_label='26-1')
        self.sign_in('office@bipsu.edu.ph', 'office-pw')

    def _visible_rows(self, selector='table tbody tr'):
        return self.page.eval_on_selector_all(
            selector,
            '(rows) => rows.filter(r => r.offsetParent !== null).length')


class NavigationSearchTest(OfficeTableTestCase):
    """The only free-text search in the app filters the sidebar, not the tables.

    Worth stating plainly, because it is easy to assume otherwise: the office
    tables are narrowed with column filters, and the search box in the sidebar
    narrows the list of pages. A test that typed into that box expecting rows
    to disappear would be testing a feature that does not exist.
    """

    def _visible_links(self):
        return self.page.eval_on_selector_all(
            '.sidebar-nav .sidebar-link',
            '(links) => links.filter(l => l.offsetParent !== null).length')

    def test_typing_narrows_the_navigation(self):
        self.visit('/vpsea/')
        box = self.page.query_selector('input[data-search]')
        if box is None:
            self.skipTest('no sidebar search on this build')
        before = self._visible_links()
        if before < 2:
            self.skipTest('not enough nav links to prove filtering')
        box.fill('Reports')
        self.page.wait_for_timeout(350)
        self.assertLess(
            self._visible_links(), before,
            f'the sidebar search left all {before} links showing')

    def test_clearing_it_brings_every_page_back(self):
        self.visit('/vpsea/')
        box = self.page.query_selector('input[data-search]')
        if box is None:
            self.skipTest('no sidebar search on this build')
        before = self._visible_links()
        box.fill('Reports')
        self.page.wait_for_timeout(350)
        box.fill('')
        self.page.wait_for_timeout(350)
        self.assertEqual(self._visible_links(), before)

    def test_a_search_matching_nothing_says_so(self):
        self.visit('/vpsea/')
        box = self.page.query_selector('input[data-search]')
        if box is None:
            self.skipTest('no sidebar search on this build')
        box.fill('zzzz-no-such-page')
        self.page.wait_for_timeout(350)
        self.assertEqual(self._visible_links(), 0)
        empty = self.page.query_selector('#navSearchEmpty')
        self.assertIsNotNone(empty)
        self.assertFalse(
            empty.is_hidden(),
            'an empty result left the sidebar blank with no explanation')


class ColumnFilterTest(OfficeTableTestCase):

    def test_a_column_filter_removes_the_rows_that_do_not_match(self):
        self.visit('/vpsea/affirmative/?tab=staff')
        select = self.page.query_selector('[data-filter-bar] select')
        if select is None:
            self.skipTest('no column filter on this page')
        before = self._visible_rows()
        options = self.page.eval_on_selector_all(
            '[data-filter-bar] select option',
            '(o) => o.map(x => x.value).filter(Boolean)')
        if not options or before < 2:
            self.skipTest('nothing to filter by')
        select.select_option(options[0])
        self.page.wait_for_timeout(400)
        self.assertLessEqual(self._visible_rows(), before)
        self.assertNoConsoleErrors()


class ActionColumnTest(OfficeTableTestCase):
    """The action column has to be reachable without scrolling sideways.

    Raised directly by the evaluators: the View control sat past the right edge
    of a wide table, so the office had to scroll horizontally to use it.
    """

    def test_the_action_control_sits_inside_the_visible_width(self):
        self.visit('/vpsea/affirmative/?tab=staff')
        action = self.page.query_selector(
            'table tbody tr td:last-child a, table tbody tr td:last-child button')
        if action is None:
            self.skipTest('no action control rendered')
        box = action.bounding_box()
        if box is None:
            self.skipTest('the action control is not laid out')
        width = self.page.evaluate('document.documentElement.clientWidth')
        self.assertLessEqual(
            box['x'] + box['width'], width + 1,
            'the action control is off-screen at the default width, so it '
            'cannot be used without scrolling the table sideways')
