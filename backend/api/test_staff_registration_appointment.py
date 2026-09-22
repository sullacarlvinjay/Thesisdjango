from django.test import Client, TestCase

from api.fixtures_registration import a_staff_member
from api.models import (ApplicantRecord, Scholarship, StaffProfile,
                        SystemSettings, User)


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


class RegisteringIsEnoughToBeListedTest(TestCase):
    """Registering as a regular employee puts you on the eligibility list.

    The programme asks an employee one thing and registration answers it, with
    the appointment paper behind the answer. An application is therefore not
    what makes somebody eligible - it only records that they asked, which the
    list shows in its own column.
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

    def _listed(self, **overrides):
        from api.views_ranking import _staff_ranking_data

        self.c.post('/register/', a_staff_member(**overrides))
        self.assertTrue(
            StaffProfile.objects.filter(
                user__email=a_staff_member()['email']).exists(),
            'the account was not created, so this proves nothing')
        return _staff_ranking_data()

    def test_a_regular_employee_is_eligible_without_applying(self):
        data = self._listed()
        self.assertEqual(len(data['rows']), 1)
        entry = data['rows'][0]
        self.assertEqual(entry.recommendation, 'Eligible')
        self.assertFalse(
            entry.applied,
            'somebody who never applied was counted as having applied')

    def test_the_appointment_paper_travels_with_them(self):
        data = self._listed()
        self.assertTrue(
            data['rows'][0].application.appointment_paper,
            'the entry carries no evidence behind its eligibility')

    def test_a_job_order_employee_is_listed_as_not_eligible(self):
        data = self._listed(employment_status='Job Order',
                            years_of_service='', date_of_regularization='')
        self.assertEqual(data['rows'], [])
        self.assertEqual(len(data['refused']), 1)
        self.assertEqual(data['refused'][0].recommendation, 'Not Eligible')

    def test_an_employee_who_applies_is_listed_once_and_marked(self):
        self.c.post('/register/', a_staff_member())
        user = User.objects.get(email=a_staff_member()['email'])
        record = ApplicantRecord.objects.create(
            full_name=user.get_full_name(), email=user.email,
            qualified_for='Staff', status='Pending Validation', course='BSIT',
            year_level=1, school_year='2026-2027', semester='2nd Semester',
            term_label='26-2')
        record.is_nsu_staff = True
        record.student_id = a_staff_member()['school_id']
        record.employment_status = 'Regular'
        record.save()

        from api.views_ranking import _staff_ranking_data
        data = _staff_ranking_data()
        self.assertEqual(
            data['total'], 1,
            'the roster listed an employee who had already applied, so they '
            'appear twice')
        self.assertTrue(data['rows'][0].applied)

    def test_registering_writes_no_applicant_record(self):
        from api.models import ApplicantRecord

        self.c.post('/register/', a_staff_member())
        self.assertFalse(
            ApplicantRecord.objects.filter(qualified_for='Staff').exists(),
            'registration filed an application on the employee behalf')
