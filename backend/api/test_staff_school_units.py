"""Where an employee works is a wider question than where a student enrols.

``BIPSU_SCHOOLS`` is the student list, and everything on it has courses under it
in ``BIPSU_COURSES`` — the Course dropdown on the registration form is built
from them and is required, so a school with no courses is one a student can pick
and then be unable to finish the form.

Half of what an employee can be assigned to has no courses and never will: the
four vice-presidential clusters, the two lifelong-learning offices, the library.
Nor do the graduate and professional schools, the Biliran campus's own
teacher-education unit, or NSTP, which every student takes and none majors in.

So the staff side reads ``BIPSU_STAFF_UNITS``, which is the student list plus
both of those groups — and this file checks the two lists stay apart, because
merging them is the obvious tidy-up and it would break student registration.

The staff field is **typed, not picked**. Registration asks for it as plain
text with nothing offered alongside — somebody signing up knows where they
work, and a list of eighty units in front of that answer only slowed them down.
My Profile still offers the groups as a ``<datalist>``, because correcting a
school later is the place a canonical spelling is worth suggesting.

The model no longer enumerates the units either, so what a form *offers* and
what it *accepts* are no longer the same question, and the checks below ask
both.
"""
from django.test import Client, TestCase

from api.constants import (
    BIPSU_COURSES, BIPSU_OFFICES, BIPSU_SCHOOLS, BIPSU_STAFF_UNIT_GROUPS,
    BIPSU_STAFF_UNITS, BIPSU_TEACHING_UNITS,
)
from api.models import StaffEmployment, StaffProfile, SystemSettings, User
from api.test_registration_payload import a_staff_member


def values(pairs):
    return [value for value, _label in pairs]


class TheTwoListsStayApartTest(TestCase):
    def test_every_student_school_has_courses_under_it(self):
        """The rule that keeps the offices off the student list. A school with
        no courses leaves a required dropdown a student cannot answer."""
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
        """The dropdown draws the groups and the model validates the flat list,
        so a unit in one and not the other is a choice nobody can save."""
        grouped = [value for _name, units in BIPSU_STAFF_UNIT_GROUPS
                   for value in values(units)]
        self.assertEqual(sorted(grouped), sorted(values(BIPSU_STAFF_UNITS)))

    def test_a_value_is_its_own_label(self):
        """These are stored as typed and printed as stored — a report reads the
        value, so a value that is not the label is a report nobody recognises."""
        for value, label in BIPSU_STAFF_UNITS:
            with self.subTest(unit=value):
                self.assertEqual(value, label)

    def test_the_model_does_not_enumerate_what_may_be_typed(self):
        """The field is typed into now, so ``choices`` would refuse a unit the
        university created after this list was last edited — which is the case
        the change exists for. On StaffEmployment, where the column actually
        lives: StaffProfile.school is a DetailField proxy onto it, so _meta
        cannot see it there any more than a queryset can."""
        self.assertIsNone(StaffEmployment._meta.get_field('school').choices)


class TheStaffFormJustTakesWhatIsTypedTest(TestCase):
    """Registration asks for the unit as free text — no list, nothing to pick
    from. Whatever the employee types is what gets stored."""

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.c = Client()

    def _form(self):
        return self.c.get('/register/').content.decode()

    def test_the_field_is_a_plain_text_input(self):
        html = self._form()
        self.assertIn('<label>Office / College / Unit</label>', html)
        self.assertIn('name="staff_school"', html)

    def test_nothing_is_offered_alongside_it(self):
        """The datalist is gone from this page. It is still on My Profile, so
        the id being absent *here* is the whole check."""
        html = self._form()
        self.assertNotIn('bipsuStaffUnits', html)
        self.assertNotIn('<datalist', html)

    def test_no_office_reaches_this_page_at_all(self):
        """The offices only ever appeared here as suggestions for this field.
        With those gone, a page still naming one is a list left behind."""
        from django.utils.html import escape

        html = self._form()
        for office in values(BIPSU_OFFICES):
            with self.subTest(unit=office):
                self.assertNotIn(escape(office), html)

    def test_the_student_dropdown_is_left_alone(self):
        """The student school picker is still a dropdown and still reads the
        student list. An office in it is a school nobody can pick a course from."""
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
        """The whole reason the field stopped being a dropdown. A closed list
        turns a reorganisation into a registration nobody can finish."""
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
        """An error that names a field nobody can find is no error, and this
        one is labelled "Office / College / Unit" now."""
        data = a_staff_member(email='none@bipsu.edu.ph')
        del data['staff_school']
        r = self.c.post('/register/', data)
        self.assertContains(r, 'Office / College / Unit is required')
        self.assertFalse(User.objects.filter(email='none@bipsu.edu.ph').exists())


class TheStaffProfileOffersThemTooTest(TestCase):
    """The other place an employee sets it — their own record, which is where a
    school recorded at registration gets corrected."""

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
        self.assertIn('<label>Office / College / Unit</label>', html)
        self.assertIn('list="bipsuStaffUnits"', html)
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
