"""A BiPSU employee is not a student of this system.

The Staff Scholarship is applied for on the staff portal and recorded as an
``AffirmativeStaffApplication``. That row *is* the award: the Staff archive tab,
the masterlist's BiPSU STAFF block and the reports all read it directly.

Approving one used to also build a Django account with ``role='student'``, a
``StudentProfile`` numbered ``AFF-<id>`` when the employee had no student
number, and an ``Application`` nothing reads. Every screen that walks
``StudentProfile`` then listed the employee as a student — My Students, the No
Scholarship archive tab, and the TES recommendation the SDSO sends onward to
UniFAST, where a BiPSU employee was sitting on a subsidy list for students.

The second half of the same fault: the TES list ranked *every* profile, with no
filter at all, so a registrant the office had rejected was on it too.
"""
from django.test import Client, TestCase

from api.models import (
    AffirmativeStaffApplication, Application, Scholarship, StudentProfile,
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

        self.application = AffirmativeStaffApplication.objects.create(
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
        """It carried a password derived from the employee's own number."""
        self.approve()
        self.assertFalse(User.objects.filter(email='norma@bipsu.edu.ph').exists())

    def test_no_second_award_row_is_written(self):
        """The staff application is the award. An Application beside it would be
        the same scholar recorded twice, in a table the Staff tab never reads."""
        self.approve()
        self.assertEqual(Application.objects.count(), 0)

    def test_the_employee_does_not_appear_on_the_tes_recommendation(self):
        """The list that leaves the building."""
        self.approve()
        data = _tes_ranking_data()
        listed = [e.student_name for e in data['rows'] + data['needs_info']]
        self.assertEqual(listed, [], f'a staff scholar reached the TES list: {listed}')

    def test_the_scholar_still_reaches_the_staff_archive(self):
        """Removing the account must not cost the office the award itself."""
        self.approve()
        html = self.c.get('/vpsea/archives/', {'type': 'Staff'}).content.decode()
        self.assertIn('Norma Duallo', html)


class TheTesListCoversVerifiedStudentsOnlyTest(TestCase):
    """A person who cannot sign in cannot be put forward for a subsidy."""

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

    def listed(self):
        data = _tes_ranking_data()
        return {e.student_id for e in data['rows'] + data['needs_info']}

    def test_a_verified_student_is_screened(self):
        self.student('Lim', '2026-0001', 'approved')
        self.assertEqual(self.listed(), {'2026-0001'})

    def test_a_registrant_still_in_the_queue_is_not(self):
        self.student('Cruz', '2026-0002', 'pending')
        self.assertEqual(self.listed(), set())

    def test_a_rejected_registrant_is_not(self):
        self.student('Reyes', '2026-0003', 'rejected')
        self.assertEqual(self.listed(), set())

    def test_the_counts_follow_the_same_list(self):
        """A total that counted people the table does not show would be the
        office's own cross-check disagreeing with the page under it."""
        self.student('Lim', '2026-0001', 'approved')
        self.student('Cruz', '2026-0002', 'pending')
        self.assertEqual(_tes_ranking_data()['total'], 1)


class PruningWhatTheOldBranchLeftBehindTest(TestCase):
    """`manage.py prune_staff_student_profiles`, which clears up the records the
    approval branch made before it was removed.

    Deployments that ran the old code still carry them, and Render's free plan
    has no shell — so the command has to be safe to run against a production
    database from a laptop, which means it has to be exactly as careful as these
    tests demand.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[])

        # What the old branch produced: the award, plus a student identity.
        self.award = AffirmativeStaffApplication.objects.create(
            full_name='Norma Duallo', email='norma@bipsu.edu.ph',
            qualified_for='Staff', status='Approved', is_nsu_staff=True)
        phantom = User.objects.create_user(
            username='norma@bipsu.edu.ph', email='norma@bipsu.edu.ph',
            password='pw', first_name='Norma', last_name='Duallo',
            role='student')
        self.phantom = StudentProfile.objects.create(
            user=phantom, student_id=f'AFF-{self.award.id}', course='MAEd')

        # A real student, who must survive untouched.
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
        """The default is a report. Somebody has to read the list first."""
        output = self.run_command()
        self.assertIn('Dry run', output)
        self.assertIn(f'AFF-{self.award.id}', output)
        self.assertTrue(StudentProfile.objects.filter(pk=self.phantom.pk).exists())

    def test_delete_removes_the_invented_record_and_its_account(self):
        self.run_command('--delete')
        self.assertFalse(StudentProfile.objects.filter(pk=self.phantom.pk).exists())
        self.assertFalse(User.objects.filter(email='norma@bipsu.edu.ph').exists())

    def test_the_staff_award_itself_survives(self):
        """The whole point: the employee keeps the scholarship. Only the student
        identity nobody asked for goes."""
        self.run_command('--delete')
        self.award.refresh_from_db()
        self.assertEqual(self.award.status, 'Approved')
        self.assertEqual(
            AffirmativeStaffApplication.objects.filter(qualified_for='Staff').count(), 1)

    def test_a_real_student_is_never_touched(self):
        self.run_command('--delete')
        self.assertTrue(StudentProfile.objects.filter(pk=self.real.pk).exists())
        self.assertTrue(User.objects.filter(email='ana@bipsu.edu.ph').exists())

    def test_a_dependents_claim_is_reported_not_removed(self):
        """A staff member's dependent may be a genuine BiPSU student, and their
        address owns a Staff application just as an employee's does. What tells
        them apart is who filed it: is_nsu_staff means the employee applied for
        themselves, and an employee is not a student under any reading."""
        user = User.objects.create_user(
            username='kid@bipsu.edu.ph', email='kid@bipsu.edu.ph', password='pw',
            first_name='Kid', last_name='Duallo', role='student')
        dependent = StudentProfile.objects.create(
            user=user, student_id='2026-0002', course='BSIT')
        AffirmativeStaffApplication.objects.create(
            full_name='Kid Duallo', email='kid@bipsu.edu.ph',
            qualified_for='Staff', status='Pending Validation',
            is_nsu_dependent=True)

        output = self.run_command('--delete')
        self.assertIn('Worth a look', output)
        self.assertIn('2026-0002', output)
        self.assertTrue(StudentProfile.objects.filter(pk=dependent.pk).exists())

    def test_it_says_so_when_the_account_has_actually_been_used(self):
        """A person signing in with it changes the decision, so it is on screen
        rather than left for the operator to find out afterwards."""
        from django.utils import timezone
        self.phantom.user.last_login = timezone.now()
        self.phantom.user.save(update_fields=['last_login'])
        self.assertIn('signed in', self.run_command())

    def test_running_it_twice_is_harmless(self):
        self.run_command('--delete')
        self.assertIn('Nothing to remove', self.run_command('--delete'))

    def test_an_affirmative_scholars_aff_number_is_never_swept_up(self):
        """Approving an Affirmative application still mints an 'AFF-<id>'
        student number, and that scholar is a real student. An earlier draft of
        this command pruned on the prefix alone and would have deleted them."""
        user = User.objects.create_user(
            username='aff@bipsu.edu.ph', email='aff@bipsu.edu.ph', password='pw',
            first_name='Rosa', last_name='Mendoza', role='student')
        scholar = StudentProfile.objects.create(
            user=user, student_id='AFF-99', course='BSED')
        AffirmativeStaffApplication.objects.create(
            full_name='Rosa Mendoza', email='aff@bipsu.edu.ph',
            qualified_for='Affirmative', status='Approved')

        self.run_command('--delete')
        self.assertTrue(StudentProfile.objects.filter(pk=scholar.pk).exists(),
                        'an Affirmative scholar was pruned as a phantom')


class AnAffirmativeScholarStillGetsTheirStudentRecordTest(TestCase):
    """The other programme on the same queue, and the line between them.

    Affirmative Action is a *student* programme — the four target groups are
    read off a student's own record and AffirmativeRecommendation hangs off
    StudentProfile — so approving one still builds the student account the rest
    of the system reads them through. BiPSU Staff is the one whose scholars are
    employees, and it is the only one excluded.
    """

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
        application = AffirmativeStaffApplication.objects.create(
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
        """The two run through the same branch, and only one of them is a
        student. This is the whole of the distinction, asserted side by side so
        neither can be changed without the other being considered."""
        self.approve('Staff')
        self.assertFalse(
            StudentProfile.objects.filter(user__email='staff@bipsu.edu.ph').exists())
