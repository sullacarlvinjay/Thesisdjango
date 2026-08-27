"""The BiPSU Staff 'My Profile' page reads and writes the staff member's own record.

Employment details used to be written into whichever AffirmativeStaffApplication
was found by email address. They live on StaffProfile now; the application is
the snapshot the office reviewed and this page must not touch it.
"""
from datetime import date

from django.test import TestCase, Client

from api.models import AffirmativeStaffApplication, StaffProfile, User


class StaffProfileEmploymentFieldsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff@bipsu.edu.ph', email='staff@bipsu.edu.ph', password='pw',
            first_name='Maria', last_name='Santos', role='nsu_staff',
        )
        self.app = AffirmativeStaffApplication.objects.create(
            full_name='Maria Santos', email='staff@bipsu.edu.ph',
            date_of_birth='1990-01-01', course='—', year_level=1,
            qualified_for='Staff', status='Approved', is_nsu_staff=True,
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='staff@bipsu.edu.ph', password='pw'))

    def _post(self, **overrides):
        data = {
            'first_name': 'Maria', 'last_name': 'Santos',
            'employment_status': 'Regular', 'designation': 'Teaching',
            'years_of_service': '12', 'date_of_regularization': '2016-06-01',
        }
        data.update(overrides)
        return self.c.post('/nsu-staff/profile/', data)

    def _profile(self):
        return StaffProfile.objects.get(user=self.user)

    def test_the_page_creates_the_profile_for_a_staff_account_without_one(self):
        StaffProfile.objects.filter(user=self.user).delete()
        r = self.c.get('/nsu-staff/profile/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(StaffProfile.objects.filter(user=self.user).exists())

    def test_the_four_employment_fields_save(self):
        r = self._post()
        self.assertEqual(r.status_code, 200)
        staff = self._profile()
        self.assertEqual(staff.employment_status, 'Regular')
        self.assertEqual(staff.designation, 'Teaching')
        self.assertEqual(staff.declared_years_of_service, 12)
        self.assertEqual(staff.date_of_regularization, date(2016, 6, 1))

    def test_the_reviewed_application_is_left_alone(self):
        self._post(department='School of Engineering')
        self.app.refresh_from_db()
        self.assertEqual(self.app.employment_status, '')
        self.assertEqual(self.app.designation, '')
        self.assertEqual(self.app.department, '')

    def test_personal_details_save_and_the_initial_is_derived(self):
        self._post(middle_name='Ramirez', suffix='Jr.', civil_status='Married',
                   contact_number='09181234567')
        staff = self._profile()
        self.assertEqual(staff.middle_name, 'Ramirez')
        self.assertEqual(staff.middle_initial, 'R.')
        self.assertEqual(staff.full_name, 'Santos Jr., Maria R.')
        self.assertEqual(staff.civil_status, 'Married')

    def test_saved_values_come_back_selected_on_the_form(self):
        self._post()
        html = self.c.get('/nsu-staff/profile/').content.decode()
        self.assertIn('<option value="Regular" selected>Regular</option>', html)
        self.assertIn('<option value="Teaching" selected>Teaching</option>', html)
        self.assertIn('value="12"', html)
        self.assertIn('value="2016-06-01"', html)

    def test_zero_years_of_service_renders_as_zero_not_blank(self):
        self._post(years_of_service='0')
        self.assertEqual(self._profile().declared_years_of_service, 0)
        html = self.c.get('/nsu-staff/profile/').content.decode()
        self.assertIn('name="years_of_service"', html)
        self.assertIn('value="0"', html)

    def test_a_date_hired_counts_the_years_instead_of_the_typed_number(self):
        self._post(date_hired='2016-06-01', years_of_service='99')
        staff = self._profile()
        expected = date.today().year - 2016 - ((date.today().month, date.today().day) < (6, 1))
        self.assertEqual(staff.years_of_service, expected)
        html = self.c.get('/nsu-staff/profile/').content.decode()
        # The typed count is no longer asked for once the hiring date is known.
        self.assertNotIn('name="years_of_service"', html)

    def test_fields_can_be_cleared_again(self):
        self._post()
        self._post(employment_status='', designation='',
                   years_of_service='', date_of_regularization='')
        staff = self._profile()
        self.assertEqual(staff.employment_status, '')
        self.assertEqual(staff.designation, '')
        self.assertIsNone(staff.declared_years_of_service)
        self.assertIsNone(staff.date_of_regularization)

    def test_bad_input_is_reported_instead_of_crashing(self):
        r = self._post(years_of_service='abc', date_of_regularization='not-a-date')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Years of service must be a whole number')
        self.assertContains(r, 'Date of regularization must be a valid date')
        self.assertNotContains(r, 'Profile saved successfully')
        staff = self._profile()
        self.assertIsNone(staff.declared_years_of_service)
        self.assertIsNone(staff.date_of_regularization)
        # The valid fields in the same submission still went through.
        self.assertEqual(staff.employment_status, 'Regular')

    def test_an_employee_id_already_on_another_record_is_refused(self):
        other = User.objects.create_user(
            username='other@bipsu.edu.ph', email='other@bipsu.edu.ph', password='pw',
            first_name='Jose', last_name='Reyes', role='nsu_staff',
        )
        StaffProfile.objects.create(user=other, employee_id='32-1-213313')
        r = self._post(employee_id='32-1-213313')
        self.assertContains(r, 'already on another staff record')
        self.assertEqual(self._profile().employee_id, '')


class StaffProfileVisibilityTest(TestCase):
    """The employment section belongs to the employee, not to an application."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='staff2@bipsu.edu.ph', email='staff2@bipsu.edu.ph', password='pw',
            first_name='Jose', last_name='Reyes', role='nsu_staff',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='staff2@bipsu.edu.ph', password='pw'))

    def _record(self, status):
        return AffirmativeStaffApplication.objects.create(
            full_name='Jose Reyes', email='staff2@bipsu.edu.ph',
            date_of_birth='1985-03-02', course='—', year_level=1,
            qualified_for='Staff', status=status, is_nsu_staff=True,
            employment_status='Contractual', designation='Non-Teaching',
        )

    def test_employment_details_are_editable_before_any_application(self):
        r = self.c.get('/nsu-staff/profile/')
        self.assertContains(r, 'name="employment_status"')
        self.assertContains(r, 'name="employee_id"')
        # The apply CTA still shows — there is genuinely no application yet.
        self.assertContains(r, 'have not applied for the')
        self.assertContains(r, 'href="/nsu-staff/apply/"')

    def test_pending_application_shows_its_status_read_only(self):
        self._record('Pending Validation')
        r = self.c.get('/nsu-staff/profile/')
        self.assertContains(r, 'name="employment_status"')
        self.assertContains(r, 'name="designation"')
        self.assertContains(r, 'name="date_of_regularization"')
        self.assertContains(r, 'value="Pending Validation"')

    def test_needs_revision_application_is_editable_too(self):
        self._record('Needs Revision')
        r = self.c.get('/nsu-staff/profile/')
        self.assertContains(r, 'name="employment_status"')
        r = self.c.post('/nsu-staff/profile/', {
            'first_name': 'Jose', 'last_name': 'Reyes',
            'employment_status': 'Regular', 'designation': 'Teaching',
        })
        self.assertContains(r, 'Profile saved successfully')
        self.assertEqual(StaffProfile.objects.get(user=self.user).employment_status, 'Regular')
