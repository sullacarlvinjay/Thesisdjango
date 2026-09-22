from django.test import Client, TestCase

from api.fixtures_registration import a_staff_member
from api.models import Scholarship, StaffProfile, SystemSettings, User


class StaffRegistrationRecordsTheAppointmentTest(TestCase):
    """Registration asks for the appointment, so applying does not.

    The Staff Scholarship turns on one answer - whether the appointment is
    regular - and the apply form already prefills it from the staff profile.
    It was never collected at registration, so the first application had to
    ask for it and the office could not read an employee's eligibility until
    they applied.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
            accepting_applications=True)
        self.c = Client()

    def _register(self, **overrides):
        return self.c.post('/register/', a_staff_member(**overrides))

    def _profile(self):
        return StaffProfile.objects.filter(
            user__email=a_staff_member()['email']).first()

    def test_a_regular_appointment_is_saved_to_the_profile(self):
        self._register()
        profile = self._profile()
        self.assertIsNotNone(profile, 'the staff account was not created')
        self.assertEqual(profile.employment_status, 'Regular')
        self.assertEqual(profile.designation, 'Teaching')
        self.assertEqual(profile.declared_years_of_service, 11)
        self.assertEqual(str(profile.date_of_regularization), '2015-06-01')

    def test_the_appointment_is_required(self):
        self._register(employment_status='')
        self.assertIsNone(
            self._profile(),
            'an account was created with no appointment recorded')

    def test_a_regular_appointment_must_carry_its_dates(self):
        self._register(date_of_regularization='')
        self.assertIsNone(
            self._profile(),
            'a regular appointment was accepted with no regularisation date')

    def test_a_job_order_is_not_asked_for_a_regularisation_date(self):
        self._register(employment_status='Job Order',
                       years_of_service='', date_of_regularization='')
        profile = self._profile()
        self.assertIsNotNone(
            profile,
            'a job order employee could not register for want of a date '
            'their appointment never had')
        self.assertEqual(profile.employment_status, 'Job Order')
        self.assertIsNone(profile.date_of_regularization)


class TheApplyFormOpensPrefilledTest(TestCase):
    """What registration recorded, the apply form should not ask again."""

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
            accepting_applications=True)
        self.user = User.objects.create_user(
            username='rosa@bipsu.edu.ph', email='rosa@bipsu.edu.ph',
            password='pw', first_name='Rosa', last_name='Delgado',
            role='nsu_staff')
        profile = StaffProfile.objects.create(
            user=self.user, employee_id='32-1-213313')
        profile.employment_status = 'Regular'
        profile.designation = 'Teaching'
        profile.declared_years_of_service = 11
        profile.date_of_regularization = '2015-06-01'
        profile.save()
        self.c = Client()
        self.assertTrue(self.c.login(email='rosa@bipsu.edu.ph', password='pw'))

    def test_the_employment_answers_come_back_on_the_form(self):
        prefill = self.c.get('/nsu-staff/apply/').context['prefill']
        self.assertEqual(prefill['employment_status'], 'Regular')
        self.assertEqual(prefill['designation'], 'Teaching')
        self.assertEqual(prefill['years_of_service'], 11)
        self.assertEqual(prefill['date_of_regularization'], '2015-06-01')

    def test_a_dependent_application_prefills_the_same_appointment(self):
        prefill = self.c.get(
            '/nsu-staff/apply/?applicant_kind=dependent').context['prefill']
        self.assertEqual(prefill['employment_status'], 'Regular')
        self.assertEqual(prefill['employee_number'], '32-1-213313')

    def test_the_dependent_form_does_not_prefill_the_employees_identity(self):
        prefill = self.c.get(
            '/nsu-staff/apply/?applicant_kind=dependent').context['prefill']
        self.assertEqual(
            prefill['first_name'], '',
            "the employee's own name was prefilled into their dependent's")
        self.assertEqual(prefill['student_number'], '')
