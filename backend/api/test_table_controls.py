from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    AcademicRenewal, AffirmativeStaffApplication, Application, Scholarship,
    StudentProfile, SystemSettings, User,
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
        student.decide_verification('approved', 'Welcome.', officer)

        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def html(self, url):
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200, url)
        return r.content.decode()

    def test_the_review_tables_declare_themselves_sortable(self):
        for url in ('/vpsea/affirmative/', '/vpsea/renewals/', '/vpsea/accounts/',
                    '/vpsea/archives/?type=Academic'):
            self.assertIn('data-sortable', self.html(url), url)

    def test_every_page_with_a_sortable_table_loads_the_sort_script(self):
        for url in ('/vpsea/affirmative/', '/vpsea/renewals/', '/vpsea/accounts/',
                    '/vpsea/archives/?type=Academic'):
            self.assertIn('js/table-sort', self.html(url), url)

    def test_the_actions_column_is_not_offered_as_a_sort(self):
        html = self.html('/vpsea/archives/?type=Academic')
        self.assertIn('data-no-sort>Actions</th>', html)

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
        html = self.html('/vpsea/affirmative/')
        self.assertIn('data-filter-search="#searchInput"', html)
        self.assertIn('id="searchInput"', html)

    def test_the_hand_written_status_menu_is_gone(self):
        html = self.html('/vpsea/affirmative/')
        self.assertNotIn('id="statusFilter"', html)
        self.assertNotIn('filterTable()', html)

    def test_the_staff_table_groups_course_by_school_too(self):
        AffirmativeStaffApplication.objects.create(
            full_name='Rey Cruz', contact_number='09171234567',
            date_of_birth=date(2000, 1, 1), course='BSN',
            qualified_for='Staff', is_nsu_staff=True)
        html = self.html('/vpsea/affirmative/?tab=staff')
        self.assertIn('data-filter="Course" data-filter-group="School"', html)
        self.assertIn('data-group="School of Nursing and Health Sciences"', html)

    def test_the_academic_table_keeps_the_school_column_it_already_had(self):
        html = self.html('/vpsea/affirmative/')
        self.assertIn('data-filter="School"', html)
        self.assertNotIn('data-filter-group', html)


class ProgramGroupingTest(TestCase):
    def test_a_staff_applicant_course_names_its_own_school(self):
        app = AffirmativeStaffApplication(
            full_name='Rey Cruz', contact_number='09171234567',
            date_of_birth=date(2000, 1, 1), course='BSCrim')
        self.assertEqual(app.course_school, 'School of Criminal Justice Education')

    def test_a_recorded_staff_school_is_believed_over_the_course(self):
        app = AffirmativeStaffApplication(
            full_name='Rey Cruz', contact_number='09171234567',
            date_of_birth=date(2000, 1, 1), course='BSCrim',
            school='School of Engineering')
        self.assertEqual(app.course_school, 'School of Engineering')
