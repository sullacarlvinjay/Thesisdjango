from django.test import Client, TestCase

from api.constants import (
    BIPSU_COURSES, BIPSU_OFFICES, BIPSU_SCHOOLS, BIPSU_STAFF_UNIT_GROUPS,
    BIPSU_STAFF_UNITS, BIPSU_TEACHING_UNITS,
)
from api.models import StaffEmployment, StaffProfile, SystemSettings, User
from api.fixtures_registration import a_staff_member
from api.fixtures_portal import labelled_control


def values(pairs):
    return [value for value, _label in pairs]


class TheTwoListsStayApartTest(TestCase):
    def test_every_student_school_has_courses_under_it(self):
        for school in values(BIPSU_SCHOOLS):
            with self.subTest(school=school):
                self.assertTrue(BIPSU_COURSES.get(school),
                                f'{school} is offered to students with no courses under it')

    def test_no_office_is_offered_to_a_student(self):
        for office in values(BIPSU_OFFICES) + values(BIPSU_TEACHING_UNITS):
            with self.subTest(unit=office):
                self.assertNotIn(office, values(BIPSU_SCHOOLS))

    def test_the_staff_list_is_every_school_plus_both_groups(self):
        self.assertEqual(
            values(BIPSU_STAFF_UNITS),
            values(BIPSU_SCHOOLS) + values(BIPSU_TEACHING_UNITS) + values(BIPSU_OFFICES))

    def test_the_groups_add_up_to_the_flat_list(self):
        grouped = [value for _name, units in BIPSU_STAFF_UNIT_GROUPS
                   for value in values(units)]
        self.assertEqual(sorted(grouped), sorted(values(BIPSU_STAFF_UNITS)))

    def test_a_value_is_its_own_label(self):
        for value, label in BIPSU_STAFF_UNITS:
            with self.subTest(unit=value):
                self.assertEqual(value, label)

    def test_the_model_does_not_enumerate_what_may_be_typed(self):
        self.assertIsNone(StaffEmployment._meta.get_field('school').choices)


class TheStaffFormJustTakesWhatIsTypedTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.c = Client()

    def _form(self):
        return self.c.get('/register/').content.decode()

    def test_the_field_is_a_plain_text_input(self):
        field = labelled_control(self._form(), 'Office / College / Unit')
        self.assertIn(
            'name="staff_school"', field,
            'the unit caption no longer reaches the unit field')

    def test_nothing_is_offered_alongside_it(self):
        html = self._form()
        self.assertNotIn('bipsuStaffUnits', html)
        self.assertNotIn('<datalist', html)

    def test_no_office_reaches_this_page_at_all(self):
        from django.utils.html import escape

        html = self._form()
        for office in values(BIPSU_OFFICES):
            with self.subTest(unit=office):
                self.assertNotIn(escape(office), html)

    def test_the_student_dropdown_is_left_alone(self):
        import re

        from django.utils.html import escape

        html = self._form()
        student = re.search(r'<select[^>]*\bname="school"[^>]*>(.*?)</select>',
                            html, re.S).group(1)
        for office in values(BIPSU_OFFICES):
            with self.subTest(office=office):
                self.assertNotIn(escape(office), student)
        self.assertNotIn('<optgroup', student)

    def test_a_unit_nobody_listed_can_still_be_registered_into(self):
        self.c.post('/register/', a_staff_member(
            email='new@bipsu.edu.ph',
            staff_school='Office of Digital Transformation',
            department='Systems', position='Analyst II'))
        staff = StaffProfile.objects.get(user__email='new@bipsu.edu.ph')
        self.assertEqual(staff.school, 'Office of Digital Transformation')

    def test_an_employee_can_register_into_an_office(self):
        self.c.post('/register/', a_staff_member(
            email='lib@bipsu.edu.ph',
            staff_school='Center for Learning Resources',
            department='Circulation', position='Librarian II'))
        staff = StaffProfile.objects.get(user__email='lib@bipsu.edu.ph')
        self.assertEqual(staff.school, 'Center for Learning Resources')

    def test_the_error_names_the_field_as_it_reads_on_screen(self):
        data = a_staff_member(email='none@bipsu.edu.ph')
        del data['staff_school']
        r = self.c.post('/register/', data)
        self.assertContains(r, 'Office / College / Unit is required')
        self.assertFalse(User.objects.filter(email='none@bipsu.edu.ph').exists())


class TheStaffProfileOffersThemTooTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        user = User.objects.create_user(
            username='t@bipsu.edu.ph', email='t@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Reyes', role='nsu_staff')
        StaffProfile.objects.create(user=user)
        self.c = Client()
        self.assertTrue(self.c.login(email='t@bipsu.edu.ph', password='pw'))

    def test_the_page_suggests_every_unit_under_its_new_label(self):
        from django.utils.html import escape

        html = self.c.get('/nsu-staff/profile/').content.decode()
        field = labelled_control(html, 'Office / College / Unit')
        self.assertIn(
            'name="school"', field,
            'the unit caption no longer reaches the unit field')
        self.assertIn('list="bipsuStaffUnits"', field)
        for _name, units in BIPSU_STAFF_UNIT_GROUPS:
            for unit in values(units):
                with self.subTest(unit=unit):
                    self.assertIn(f'<option value="{escape(unit)}">', html)

    def test_an_office_can_be_saved_there(self):
        self.c.post('/nsu-staff/profile/',
                    {'school': 'Research, Innovation, and Social Impact'})
        staff = StaffProfile.objects.get(user__email='t@bipsu.edu.ph')
        self.assertEqual(staff.school, 'Research, Innovation, and Social Impact')

    def test_a_unit_nobody_listed_can_be_saved_there_too(self):
        self.c.post('/nsu-staff/profile/', {'school': 'Binary Digital Campus'})
        staff = StaffProfile.objects.get(user__email='t@bipsu.edu.ph')
        self.assertEqual(staff.school, 'Binary Digital Campus')
