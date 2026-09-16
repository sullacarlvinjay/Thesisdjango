from django.test import Client, TestCase

from api.models import (
    ApplicantRecord, Application, Scholarship, StudentProfile,
    SystemSettings, User,
)
from api.student_views import _tes_ranking_data


class ApprovingAStaffScholarshipMakesNoStudentTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

        self.application = ApplicantRecord.objects.create(
            full_name='Norma Duallo', email='norma@bipsu.edu.ph',
            qualified_for='Staff', status='Pending Validation',
            course='MAEd', year_level=1, is_nsu_staff=True,
            employment_status='Regular')

    def approve(self):
        return self.c.post('/vpsea/affirmative/', {
            'app_id': self.application.id, 'status': 'Approved',
            'remarks': '', 'tab': 'staff'})

    def test_the_approval_is_recorded_on_the_application_itself(self):
        self.approve()
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'Approved')

    def test_no_student_profile_is_invented_for_the_employee(self):
        self.approve()
        self.assertEqual(StudentProfile.objects.count(), 0)
        self.assertFalse(StudentProfile.objects.filter(
            student_id__startswith='AFF-').exists())

    def test_no_student_account_is_invented_either(self):
        self.approve()
        self.assertFalse(User.objects.filter(email='norma@bipsu.edu.ph').exists())

    def test_no_second_award_row_is_written(self):
        self.approve()
        self.assertEqual(Application.objects.count(), 0)

    def test_the_employee_does_not_appear_on_the_tes_recommendation(self):
        self.approve()
        data = _tes_ranking_data()
        listed = [e.student_name for e in data['rows']]
        self.assertEqual(listed, [], f'a staff scholar reached the TES list: {listed}')
        self.assertEqual(data['total'] + data['excluded'], 0)

    def test_the_scholar_still_reaches_the_staff_archive(self):
        self.approve()
        html = self.c.get('/vpsea/archives/', {'type': 'Staff'}).content.decode()
        self.assertIn('Norma Duallo', html)


class TheTesListCoversVerifiedStudentsOnlyTest(TestCase):
    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})

    def student(self, last, student_id, verification):
        user = User.objects.create_user(
            username=f'{student_id}@bipsu.edu.ph', password='pw',
            email=f'{student_id}@bipsu.edu.ph', first_name='A', last_name=last,
            role='student')
        user.verification_status = verification
        user.save(update_fields=['verification_status'])
        return StudentProfile.objects.create(
            user=user, student_id=student_id, course='BSCS', year_level=2)

    def screened(self):
        data = _tes_ranking_data()
        return data['total'] + data['excluded']

    def test_a_verified_student_is_screened(self):
        self.student('Lim', '2026-0001', 'approved')
        self.assertEqual(self.screened(), 1)

    def test_a_registrant_still_in_the_queue_is_not(self):
        self.student('Cruz', '2026-0002', 'pending')
        self.assertEqual(self.screened(), 0)

    def test_a_rejected_registrant_is_not(self):
        self.student('Reyes', '2026-0003', 'rejected')
        self.assertEqual(self.screened(), 0)

    def test_the_counts_follow_the_same_list(self):
        self.student('Lim', '2026-0001', 'approved')
        self.student('Cruz', '2026-0002', 'pending')
        data = _tes_ranking_data()
        self.assertEqual(len(data['rows']), data['total'])
        self.assertEqual(data['total'] + data['excluded'], 1)


class PruningWhatTheOldBranchLeftBehindTest(TestCase):
    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[])

        self.award = ApplicantRecord.objects.create(
            full_name='Norma Duallo', email='norma@bipsu.edu.ph',
            qualified_for='Staff', status='Approved', is_nsu_staff=True)
        phantom = User.objects.create_user(
            username='norma@bipsu.edu.ph', email='norma@bipsu.edu.ph',
            password='pw', first_name='Norma', last_name='Duallo',
            role='student')
        self.phantom = StudentProfile.objects.create(
            user=phantom, student_id=f'AFF-{self.award.id}', course='MAEd')

        real = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student')
        self.real = StudentProfile.objects.create(
            user=real, student_id='2026-0001', course='BSCS')

    def run_command(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('prune_staff_student_profiles', *args, stdout=out)
        return out.getvalue()

    def test_a_plain_run_writes_nothing(self):
        output = self.run_command()
        self.assertIn('Dry run', output)
        self.assertIn(f'AFF-{self.award.id}', output)
        self.assertTrue(StudentProfile.objects.filter(pk=self.phantom.pk).exists())

    def test_delete_removes_the_invented_record_and_its_account(self):
        self.run_command('--delete')
        self.assertFalse(StudentProfile.objects.filter(pk=self.phantom.pk).exists())
        self.assertFalse(User.objects.filter(email='norma@bipsu.edu.ph').exists())

    def test_the_staff_award_itself_survives(self):
        self.run_command('--delete')
        self.award.refresh_from_db()
        self.assertEqual(self.award.status, 'Approved')
        self.assertEqual(
            ApplicantRecord.objects.filter(qualified_for='Staff').count(), 1)

    def test_a_real_student_is_never_touched(self):
        self.run_command('--delete')
        self.assertTrue(StudentProfile.objects.filter(pk=self.real.pk).exists())
        self.assertTrue(User.objects.filter(email='ana@bipsu.edu.ph').exists())

    def test_a_dependents_claim_is_reported_not_removed(self):
        user = User.objects.create_user(
            username='kid@bipsu.edu.ph', email='kid@bipsu.edu.ph', password='pw',
            first_name='Kid', last_name='Duallo', role='student')
        dependent = StudentProfile.objects.create(
            user=user, student_id='2026-0002', course='BSIT')
        ApplicantRecord.objects.create(
            full_name='Kid Duallo', email='kid@bipsu.edu.ph',
            qualified_for='Staff', status='Pending Validation',
            is_nsu_dependent=True)

        output = self.run_command('--delete')
        self.assertIn('Worth a look', output)
        self.assertIn('2026-0002', output)
        self.assertTrue(StudentProfile.objects.filter(pk=dependent.pk).exists())

    def test_it_says_so_when_the_account_has_actually_been_used(self):
        from django.utils import timezone
        self.phantom.user.last_login = timezone.now()
        self.phantom.user.save(update_fields=['last_login'])
        self.assertIn('signed in', self.run_command())

    def test_running_it_twice_is_harmless(self):
        self.run_command('--delete')
        self.assertIn('Nothing to remove', self.run_command('--delete'))

    def test_an_affirmative_scholars_aff_number_is_never_swept_up(self):
        user = User.objects.create_user(
            username='aff@bipsu.edu.ph', email='aff@bipsu.edu.ph', password='pw',
            first_name='Rosa', last_name='Mendoza', role='student')
        scholar = StudentProfile.objects.create(
            user=user, student_id='AFF-99', course='BSED')
        ApplicantRecord.objects.create(
            full_name='Rosa Mendoza', email='aff@bipsu.edu.ph',
            qualified_for='Affirmative', status='Approved')

        self.run_command('--delete')
        self.assertTrue(StudentProfile.objects.filter(pk=scholar.pk).exists(),
                        'an Affirmative scholar was pruned as a phantom')


class AnAffirmativeScholarStillGetsTheirStudentRecordTest(TestCase):
    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        Scholarship.objects.create(
            name='Affirmative Action', type='Affirmative', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def approve(self, qualified_for):
        application = ApplicantRecord.objects.create(
            full_name='Juan Dela Cruz', email=f'{qualified_for.lower()}@bipsu.edu.ph',
            qualified_for=qualified_for, status='Pending Validation',
            course='BSIT', year_level=1)
        self.c.post('/vpsea/affirmative/', {
            'app_id': application.id, 'status': 'Approved', 'remarks': '',
            'tab': qualified_for.lower()})
        return application

    def test_an_affirmative_approval_still_builds_the_student_record(self):
        self.approve('Affirmative')
        self.assertTrue(
            StudentProfile.objects.filter(user__email='affirmative@bipsu.edu.ph').exists())

    def test_a_staff_approval_beside_it_does_not(self):
        self.approve('Staff')
        self.assertFalse(
            StudentProfile.objects.filter(user__email='staff@bipsu.edu.ph').exists())
