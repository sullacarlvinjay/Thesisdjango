"""Civil status, educational background and family background are write-once.

These three are what the masterlist exports and CHED's TES form are built from,
so once a student has entered them a later edit would quietly change a record
the office has already reviewed. They follow the same write-once rule the
address and middle name already use.

The office is the escape hatch: the archives edit screen can still correct one
that was entered wrong, which is the whole point of that screen.
"""
from django.test import Client, TestCase

from api.models import Scholarship, StudentProfile, SystemSettings, User


class LockedProfileFieldsTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[],
        )
        self.user = User.objects.create_user(
            username='stu@bipsu.edu.ph', email='stu@bipsu.edu.ph', password='pw',
            first_name='Juan', last_name='Dela Cruz', role='student',
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2024-0001', course='BSCS', year_level=2)
        self.c = Client()
        self.assertTrue(self.c.login(email='stu@bipsu.edu.ph', password='pw'))

    def _post(self, **overrides):
        data = {
            'civil_status': 'Single',
            'elementary': 'Naval Central', 'highschool': 'Biliran NHS',
            'last_school': 'Biliran NHS',
            'father_last_name': 'Dela Cruz', 'father_first_name': 'Pedro',
            'father_middle_name': 'Reyes', 'father_occupation': 'Farmer',
            'mother_last_name': 'Santos', 'mother_first_name': 'Maria',
            'mother_middle_name': 'Lim', 'mother_occupation': 'Teacher',
        }
        data.update(overrides)
        r = self.c.post('/student/profile/', data)
        self.profile.refresh_from_db()
        return r

    # ── the lock ────────────────────────────────────────────────────────────

    def test_the_first_save_is_accepted(self):
        self._post()
        self.assertEqual(self.profile.civil_status, 'Single')
        self.assertEqual(self.profile.elementary, 'Naval Central')
        self.assertEqual(self.profile.father_first_name, 'Pedro')
        self.assertEqual(self.profile.mother_occupation, 'Teacher')

    def test_a_second_save_cannot_change_civil_status(self):
        self._post()
        self._post(civil_status='Married')
        self.assertEqual(self.profile.civil_status, 'Single')

    def test_a_second_save_cannot_change_educational_background(self):
        self._post()
        self._post(elementary='Somewhere Else', highschool='Another NHS',
                   last_school='Another NHS')
        self.assertEqual(self.profile.elementary, 'Naval Central')
        self.assertEqual(self.profile.highschool, 'Biliran NHS')

    def test_a_second_save_cannot_change_family_background(self):
        self._post()
        self._post(father_first_name='Wrong', mother_occupation='Wrong')
        self.assertEqual(self.profile.father_first_name, 'Pedro')
        self.assertEqual(self.profile.mother_occupation, 'Teacher')

    def test_a_half_filled_group_stays_open(self):
        """Locking a group the student has not finished would strand them."""
        self._post(highschool='', last_school='')
        self.assertEqual(self.profile.elementary, 'Naval Central')
        self._post(elementary='Naval Central', highschool='Biliran NHS',
                   last_school='Biliran NHS')
        self.assertEqual(self.profile.highschool, 'Biliran NHS')

    def test_the_page_renders_the_locked_fields_readonly(self):
        self._post()
        r = self.c.get('/student/profile/')
        self.assertTrue(r.context['civil_status_locked'])
        self.assertTrue(r.context['education_locked'])
        self.assertTrue(r.context['family_locked'])
        self.assertContains(r, 'Educational background is locked after first save')
        self.assertContains(r, 'Family background is locked after first save')

    def test_nothing_is_locked_before_the_first_save(self):
        r = self.c.get('/student/profile/')
        self.assertFalse(r.context['civil_status_locked'])
        self.assertFalse(r.context['education_locked'])
        self.assertFalse(r.context['family_locked'])

    # ── the office override ─────────────────────────────────────────────────

    def test_the_archives_edit_can_correct_a_locked_field(self):
        self._post()
        User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea',
        )
        office = Client()
        self.assertTrue(office.login(email='vpsea@bipsu.edu.ph', password='pw'))

        office.post(f'/vpsea/archives/student/{self.profile.pk}/edit/', {
            'first_name': 'Juan', 'last_name': 'Dela Cruz',
            'course': 'BSCS', 'year_level': '2',
            'civil_status': 'Married',
            'elementary': 'Naval Central School',
            'father_first_name': 'Pedro Jr.',
        })
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.civil_status, 'Married')
        self.assertEqual(self.profile.elementary, 'Naval Central School')
        self.assertEqual(self.profile.father_first_name, 'Pedro Jr.')

    def test_a_blank_override_field_leaves_the_value_alone(self):
        """The modal renders these empty, so blank has to mean 'keep'."""
        self._post()
        User.objects.create_user(
            username='vpsea2@bipsu.edu.ph', email='vpsea2@bipsu.edu.ph',
            password='pw', role='vpsea',
        )
        office = Client()
        self.assertTrue(office.login(email='vpsea2@bipsu.edu.ph', password='pw'))

        office.post(f'/vpsea/archives/student/{self.profile.pk}/edit/', {
            'first_name': 'Juan', 'last_name': 'Dela Cruz',
            'course': 'BSCS', 'year_level': '2',
            'civil_status': '', 'elementary': '', 'mother_occupation': '',
        })
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.civil_status, 'Single')
        self.assertEqual(self.profile.elementary, 'Naval Central')
        self.assertEqual(self.profile.mother_occupation, 'Teacher')
