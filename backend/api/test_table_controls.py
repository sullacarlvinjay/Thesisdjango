"""Sorting and filter schemes on the office review tables.

The behaviour itself is in static/js/table-sort.js and static/js/table-filter.js
and runs in the browser, so what can be checked here is the contract between the
templates and those scripts: the table says it is sortable and filterable, the
columns worth narrowing by are marked, the actions column is not, and the page
actually loads the scripts.

That contract is exactly what a careless edit breaks — a heading renamed or a
table rebuilt drops the feature silently, with no error anywhere.
"""
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.constants import OTHER_PROGRAMS
from api.models import (
    AcademicRenewal, AffirmativeStaffApplication, Application, Scholarship,
    ScholarshipLinkRequest, StudentProfile, SystemSettings, TESApplication, User,
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
        self.profile = profile
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

    # ── grouped filters ─────────────────────────────────────────────────────
    #
    # A column can name the wider thing its values belong to, and the script
    # puts a dropdown for that in front of the column's own. The heading alone
    # is not the contract: with no data-group on the cells there is nothing to
    # build the School list from and it never appears at all.

    def test_the_staff_table_groups_course_by_school_too(self):
        """The staff portal asks for a course and no school, so the course
        has to name one for the dropdown to have anything in it."""
        AffirmativeStaffApplication.objects.create(
            full_name='Rey Cruz', contact_number='09171234567',
            date_of_birth=date(2000, 1, 1), course='BSN',
            qualified_for='Staff', is_nsu_staff=True)
        html = self.html('/vpsea/affirmative/?tab=staff')
        self.assertIn('data-filter="Course" data-filter-group="School"', html)
        self.assertIn('data-group="School of Nursing and Health Sciences"', html)

    def test_the_academic_table_keeps_the_school_column_it_already_had(self):
        """It shows School as a column, which is already a filter of its own.
        A grouped one beside it would be a second dropdown saying the same."""
        html = self.html('/vpsea/affirmative/')
        self.assertIn('data-filter="School"', html)
        self.assertNotIn('data-filter-group', html)


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

    def test_the_program_filter_is_grouped_by_school(self):
        """The column prints CHED registry names in full, and forty of those
        cannot be picked out of one list. School is not a column here — it
        rides along on the Program cell — so both halves have to be there.
        """
        student = User.objects.create_user(
            username='cy@bipsu.edu.ph', email='cy@bipsu.edu.ph', password='pw',
            first_name='Cy', last_name='Reyes', role='student')
        profile = StudentProfile.objects.create(
            user=student, student_id='2022-00333',
            school='School of Technologies and Computer Studies', course='BSCS')
        TESApplication.objects.create(
            student=profile,
            complete_program='BACHELOR OF SCIENCE IN COMPUTER SCIENCE')
        html = self.html('/unifast/tes-applications/')
        self.assertIn('data-filter="Program" data-filter-group="School"', html)
        self.assertIn('data-group="School of Technologies and Computer Studies"', html)


class ProgramGroupingTest(TestCase):
    """What those School dropdowns get built from.

    The grouping is worked out on read, never stored, so these are the rules the
    filter bar inherits — a wrong one files a scholar under a school that does
    not teach them, and the office narrows to it and sees nobody.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        user = User.objects.create_user(
            username='bea@bipsu.edu.ph', email='bea@bipsu.edu.ph', password='pw',
            first_name='Bea', last_name='Sy', role='student')
        self.profile = StudentProfile.objects.create(
            user=user, student_id='2022-00222',
            school='School of Teacher Education', course='BEEd')

    def test_a_registry_programme_is_matched_on_the_words_in_it(self):
        app = TESApplication.objects.create(
            student=self.profile,
            complete_program='BACHELOR OF SCIENCE IN CIVIL ENGINEERING')
        self.assertEqual(app.program_school, 'School of Engineering')

    def test_an_application_with_no_programme_follows_the_course(self):
        """The column falls back to the student's course, so the grouping has
        to as well — otherwise the row hides under every school there is."""
        app = TESApplication.objects.create(student=self.profile)
        self.assertEqual(app.program_school, 'School of Teacher Education')

    def test_a_programme_matching_no_rule_is_visible_rather_than_wrong(self):
        app = TESApplication.objects.create(
            student=self.profile, complete_program='BACHELOR OF PUPPETRY')
        self.assertEqual(app.program_school, OTHER_PROGRAMS)

    def test_a_staff_applicant_course_names_its_own_school(self):
        app = AffirmativeStaffApplication(
            full_name='Rey Cruz', contact_number='09171234567',
            date_of_birth=date(2000, 1, 1), course='BSCrim')
        self.assertEqual(app.course_school, 'School of Criminal Justice Education')

    def test_a_recorded_staff_school_is_believed_over_the_course(self):
        """The archive-add form can set one by hand; a course spelled its own
        way should not overrule what the office typed."""
        app = AffirmativeStaffApplication(
            full_name='Rey Cruz', contact_number='09171234567',
            date_of_birth=date(2000, 1, 1), course='BSCrim',
            school='School of Engineering')
        self.assertEqual(app.course_school, 'School of Engineering')
