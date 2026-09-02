"""Sorting and filter schemes on the office review tables.

The behaviour itself is in static/js/table-sort.js and static/js/table-filter.js
and runs in the browser, so what can be checked here is the contract between the
templates and those scripts: the table says it is sortable and filterable, the
columns worth narrowing by are marked, the actions column is not, and the page
actually loads the scripts.

That contract is exactly what a careless edit breaks — a heading renamed or a
table rebuilt drops the feature silently, with no error anywhere.
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    AcademicRenewal, Application, Scholarship, StudentProfile, SystemSettings, User,
)


def a_pdf(name='doc.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


class TableControlsTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        student = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student')
        profile = StudentProfile.objects.create(
            user=student, student_id='2022-00111', school='School of Engineering',
            course='BSCE', year_level=2)
        Application.objects.create(student=profile, scholarship=scholarship,
                                   status='Pending Validation')
        AcademicRenewal.objects.create(
            student=profile, certificate_of_grades=a_pdf('cog.pdf'),
            certificate_of_enrollment=a_pdf('coe.pdf'))

        officer = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        # The accounts page only draws its table once there is a decision in it.
        student.decide_verification('approved', 'Welcome.', officer)

        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def html(self, url):
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200, url)
        return r.content.decode()

    # ── sorting ─────────────────────────────────────────────────────────────

    def test_the_review_tables_declare_themselves_sortable(self):
        for url in ('/vpsea/affirmative/', '/vpsea/renewals/', '/vpsea/accounts/',
                    '/vpsea/archives/?type=Academic'):
            self.assertIn('data-sortable', self.html(url), url)

    def test_every_page_with_a_sortable_table_loads_the_sort_script(self):
        for url in ('/vpsea/affirmative/', '/vpsea/renewals/', '/vpsea/accounts/',
                    '/vpsea/archives/?type=Academic'):
            # Without the extension: the manifest storage hashes it in.
            self.assertIn('js/table-sort', self.html(url), url)

    def test_link_requests_is_left_alone_because_it_lists_cards(self):
        """There are no columns there to sort or narrow by."""
        html = self.html('/vpsea/link-requests/')
        self.assertNotIn('js/table-sort', html)
        self.assertNotIn('data-filter-bar', html)

    def test_the_actions_column_is_not_offered_as_a_sort(self):
        """There is nothing to order a column of buttons by."""
        html = self.html('/vpsea/archives/?type=Academic')
        self.assertIn('data-no-sort>Actions</th>', html)

    # ── filter schemes ──────────────────────────────────────────────────────

    def test_the_applications_table_can_be_narrowed_by_category(self):
        html = self.html('/vpsea/affirmative/')
        self.assertIn('data-filterable', html)
        self.assertIn('data-filter-bar', html)
        for column in ('School', 'Course', 'Type', 'Semester', 'Status'):
            self.assertIn(f'data-filter="{column}"', html,
                          f'{column} is not offered as a filter')

    def test_every_page_with_a_filter_bar_loads_the_filter_script(self):
        for url in ('/vpsea/affirmative/', '/vpsea/renewals/', '/vpsea/accounts/'):
            html = self.html(url)
            self.assertIn('data-filter-bar', html, url)
            self.assertIn('js/table-filter', html, url)

    def test_the_search_box_is_wired_to_the_filter_bar(self):
        """The bar owns the search too, so the two cannot disagree about a row."""
        html = self.html('/vpsea/affirmative/')
        self.assertIn('data-filter-search="#searchInput"', html)
        self.assertIn('id="searchInput"', html)

    def test_the_hand_written_status_menu_is_gone(self):
        """It listed four statuses someone typed in; the bar reads the table."""
        html = self.html('/vpsea/affirmative/')
        self.assertNotIn('id="statusFilter"', html)
        self.assertNotIn('filterTable()', html)


class UniFASTTableControlsTest(TestCase):
    """The TES Applications table gets the same scheme the SDSO tables have."""

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        Scholarship.objects.create(
            name='TES', type='TES', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
            password='pw', role='unifast')
        self.c = Client()
        self.assertTrue(self.c.login(email='unifast@bipsu.edu.ph', password='pw'))

    def html(self, url):
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200, url)
        return r.content.decode()

    def test_the_tes_table_can_be_sorted_and_narrowed(self):
        html = self.html('/unifast/tes-applications/')
        self.assertIn('data-sortable', html)
        self.assertIn('data-filterable', html)
        self.assertIn('data-filter-bar', html)
        for column in ('Program', 'Year', 'Term', 'Status'):
            self.assertIn(f'data-filter="{column}"', html,
                          f'{column} is not offered as a filter')

    def test_the_tes_page_loads_both_scripts(self):
        html = self.html('/unifast/tes-applications/')
        self.assertIn('js/table-filter', html)
        self.assertIn('js/table-sort', html)

    def test_the_tes_actions_column_is_not_offered_as_a_sort(self):
        self.assertIn('data-no-sort', self.html('/unifast/tes-applications/'))

    def test_the_tes_search_box_is_wired_to_the_filter_bar(self):
        """One script hides rows, not two — the old filterTes() fought this one."""
        html = self.html('/unifast/tes-applications/')
        self.assertIn('data-filter-search="#tesSearch"', html)
        self.assertIn('id="tesSearch"', html)
        self.assertNotIn('filterTes', html)
