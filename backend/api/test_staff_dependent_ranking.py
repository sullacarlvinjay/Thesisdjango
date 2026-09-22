from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api import staff_ranking
from api.models import (ApplicantRecord, Scholarship, StaffProfile,
                        StudentProfile, SystemSettings, User)
from api.views_ranking import _staff_ranking_data


class DependentReachesTheRankingTest(TestCase):
    """Where an employee-filed dependent lands on the office's ranking.

    The ranking is fed by every ``ApplicantRecord`` carrying
    ``qualified_for='Staff'`` for the term, not by the apply form, so a
    dependent filed through the staff portal has to arrive there on its own.
    The dependent's appointment rule reads the employee's ``StaffProfile``
    rather than the employment answers on the dependent's record, which is
    why the apply form still writes those answers back to the profile.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
            accepting_applications=True)
        self.employee = User.objects.create_user(
            username='rosa@bipsu.edu.ph', email='rosa@bipsu.edu.ph',
            password='pw', first_name='Rosa', last_name='Delgado',
            role='nsu_staff')
        StaffProfile.objects.create(user=self.employee, employee_id='EMP-0042')
        student = User.objects.create_user(
            username='mila@bipsu.edu.ph', email='mila@bipsu.edu.ph',
            password='pw', first_name='Mila', last_name='Delgado',
            role='student')
        StudentProfile.objects.create(
            user=student, student_id='2024-00311', course='BSCS',
            year_level=2, date_of_birth='2006-04-18')
        self.c = Client()
        self.assertTrue(self.c.login(email='rosa@bipsu.edu.ph', password='pw'))

    def _file_for_dependent(self, **overrides):
        form = dict(
            applicant_kind='dependent',
            first_name='Mila', last_name='Delgado',
            date_of_birth='2006-04-18', gender='Female',
            course='BSCS', year_level='2',
            student_number='2024-00311',
            relationship_to_staff='Daughter',
            employee_number='EMP-0042',
            employment_status='Regular', designation='Teaching',
            years_of_service='11', date_of_regularization='2015-06-01',
            appointment_paper=SimpleUploadedFile(
                'appointment.pdf', b'%PDF-1.4 appointment',
                content_type='application/pdf'),
        )
        form.update(overrides)
        return self.c.post('/nsu-staff/apply/', form)

    def _row_for(self, data, name):
        for bucket in ('rows', 'needs_info'):
            for evaluation in data[bucket]:
                if evaluation.applicant_name == name:
                    return bucket, evaluation
        return None, None

    def test_the_dependent_reaches_the_ranking_at_all(self):
        self._file_for_dependent()
        bucket, evaluation = self._row_for(_staff_ranking_data(), 'Mila Delgado')
        self.assertIsNotNone(
            evaluation,
            'a dependent filed through the staff portal never reached the '
            'ranking the office works from')
        self.assertEqual(evaluation.standing, staff_ranking.DEPENDENT)

    def test_the_dependent_is_counted_apart_from_employees(self):
        self._file_for_dependent()
        counts = _staff_ranking_data()['counts']
        self.assertEqual(counts['dependents'], 1)
        self.assertEqual(counts['employees'], 0)

    def test_the_appointment_rule_reads_the_employees_profile(self):
        self._file_for_dependent()
        _bucket, evaluation = self._row_for(
            _staff_ranking_data(), 'Mila Delgado')
        rule = [r for r in evaluation.rules if r.key == 'permanent'][0]
        self.assertEqual(
            rule.verdict, staff_ranking.PASS,
            'the apply form did not write the employment answers back to the '
            "employee's profile, so their dependent cannot be scored")
        self.assertIn('Rosa Delgado', rule.detail)

    def test_an_employee_with_no_appointment_on_file_is_not_refused(self):
        profile = StaffProfile.objects.get(user=self.employee)
        profile.employment_status = ''
        profile.save()
        ApplicantRecord.objects.create(
            full_name='Mila Delgado', email='mila@bipsu.edu.ph',
            qualified_for='Staff', status='Pending Validation', course='BSCS',
            year_level=2, school_year='2026-2027', semester='2nd Semester',
            term_label='26-2').save()
        record = ApplicantRecord.objects.get(full_name='Mila Delgado')
        record.is_nsu_dependent = True
        record.staff_name = 'Rosa Delgado'
        record.staff_employee_id = 'EMP-0042'
        record.relationship_to_staff = 'Daughter'
        record.student_id = '2024-00311'
        record.save()
        bucket, evaluation = self._row_for(
            _staff_ranking_data(), 'Mila Delgado')
        self.assertEqual(
            bucket, 'needs_info',
            'a dependent was refused over a question nobody asked them')
        self.assertEqual(evaluation.status, staff_ranking.FOR_VERIFICATION)


class OfficeAddedStaffRecordTest(TestCase):
    """A Staff record that never passed through the apply form.

    The archives page files one directly, with none of the employment answers
    the rules score on. It has to stay visible to the office rather than drop
    out of the list or be refused.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})

    def test_it_reaches_the_ranking_as_unverified(self):
        ApplicantRecord.objects.create(
            full_name='Pedro Ramos', email='pedro@bipsu.edu.ph',
            qualified_for='Staff', status='Approved', course='BSIT',
            year_level=1, is_nsu_staff=True, school_year='2026-2027',
            semester='2nd Semester', term_label='26-2')
        data = _staff_ranking_data()
        names = [e.applicant_name for e in data['needs_info']]
        self.assertIn(
            'Pedro Ramos', names,
            'an office-added Staff record vanished from the ranking instead '
            'of asking the office for what it lacks')
        self.assertEqual(data['counts']['not_qualified'], 0)
