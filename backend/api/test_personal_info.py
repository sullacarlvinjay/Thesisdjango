from django.test import TestCase, Client

from api.models import StaffProfile, StudentProfile, User
from api.fixtures_registration import a_staff_member, a_student


class RegistrationFormMixin:
    def setUp(self):
        self.c = Client()

    def _register(self, **overrides):
        return self.c.post('/register/', a_student(suffix='Jr.', **overrides))


class RegistrationCollectsTheMiddleNameTest(RegistrationFormMixin, TestCase):
    def test_a_student_signing_up_keeps_their_middle_name(self):
        self._register()
        profile = StudentProfile.objects.get(student_id='2022-00999')
        self.assertEqual(profile.middle_name, 'Ramirez')
        self.assertEqual(profile.middle_initial, 'R.')
        self.assertEqual(profile.suffix, 'Jr.')
        self.assertEqual(profile.full_name, 'Dela Cruz Jr., Juan R.')

    def test_no_middle_name_leaves_the_initial_blank_not_a_stray_period(self):
        user = User.objects.create_user(
            username='nomiddle@bipsu.edu.ph', email='nomiddle@bipsu.edu.ph',
            password='pw', first_name='Juan', last_name='Dela Cruz', role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id='2022-00998', course='BSCS', year_level=2)
        self.assertEqual(profile.middle_initial, '')
        self.assertEqual(profile.full_name, 'Dela Cruz, Juan')

    def test_the_form_will_not_send_without_one(self):
        r = self._register(middle_name='')
        self.assertContains(r, 'Middle Name is required')
        self.assertFalse(StudentProfile.objects.filter(student_id='2022-00999').exists())

    def test_a_staff_signing_up_gets_a_profile_of_their_own(self):
        self.c.post('/register/', a_staff_member(
            email='staff@bipsu.edu.ph', middle_name='Ramirez',
            school_id='32-1-213313', department='School of Engineering',
            position='Instructor I'))
        staff = StaffProfile.objects.get(user__email='staff@bipsu.edu.ph')
        self.assertEqual(staff.employee_id, '32-1-213313')
        self.assertEqual(staff.department, 'School of Engineering')
        self.assertEqual(staff.position, 'Instructor I')
        self.assertEqual(staff.middle_name, 'Ramirez')

    def test_the_form_asks_staff_for_the_details_the_view_reads(self):
        html = self.c.get('/register/').content.decode()
        for field in ('school_id', 'department', 'position'):
            self.assertIn(f'name="{field}"', html)

    def test_a_rejected_staff_signup_comes_back_with_them_still_filled_in(self):
        r = self.c.post('/register/', a_staff_member(
            email='staff@bipsu.edu.ph', confirm_password='different',
            school_id='32-1-213313', department='School of Engineering',
            position='Instructor I'))
        self.assertContains(r, 'Passwords do not match')
        self.assertContains(r, 'value="32-1-213313"')
        self.assertContains(r, 'value="Instructor I"')


class RegistrationSchoolTest(RegistrationFormMixin, TestCase):
    def test_the_school_picked_at_signup_is_saved(self):
        self._register()
        profile = StudentProfile.objects.get(student_id='2022-00999')
        self.assertEqual(profile.school, 'School of Technologies and Computer Studies')
        self.assertEqual(profile.course, 'BSCS')

    def test_the_form_will_not_send_without_a_school(self):
        r = self._register(school='')
        self.assertContains(r, 'School is required')
        self.assertFalse(StudentProfile.objects.filter(student_id='2022-00999').exists())

    def test_an_unrecognised_course_leaves_the_school_blank_rather_than_guessing(self):
        from api.constants import school_for_course
        self.assertEqual(school_for_course('BSCS'),
                         'School of Technologies and Computer Studies')
        self.assertEqual(
            school_for_course('Batchelor of Science in Computer Science '), '')

    def test_the_form_offers_the_schools_instead_of_a_free_text_course(self):
        html = self.c.get('/register/').content.decode()
        self.assertIn('name="school"', html)
        self.assertIn('<select name="course"', html)
        self.assertIn('School of Engineering', html)
        self.assertNotIn('placeholder="e.g. BSIT"', html)


class StudentProfilePageMiddleNameTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student',
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BS Nursing', year_level=2,
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def test_a_student_can_fill_in_the_middle_name_they_were_never_asked_for(self):
        self.c.post('/student/profile/', {'middle_name': 'Reyes'})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.middle_name, 'Reyes')
        self.assertEqual(self.profile.middle_initial, 'R.')

    def test_the_profile_does_not_show_the_derived_initial(self):
        self.c.post('/student/profile/', {'middle_name': 'Reyes'})
        html = self.c.get('/student/profile/').content.decode()
        self.assertNotIn('Middle Initial', html)
        self.assertIn('Middle Name', html)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.middle_initial, 'R.')

    def test_it_locks_once_saved_so_a_name_on_file_cannot_be_swapped(self):
        self.c.post('/student/profile/', {'middle_name': 'Reyes'})
        self.c.post('/student/profile/', {'middle_name': 'Santos'})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.middle_name, 'Reyes')
        html = self.c.get('/student/profile/').content.decode()
        self.assertIn('name="middle_name" value="Reyes"', html.replace('type="hidden" ', ''))
