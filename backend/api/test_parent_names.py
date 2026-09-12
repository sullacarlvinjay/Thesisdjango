"""Parent names live on the profile, in parts, and are entered exactly once.

StudentProfile used to hold one combined string per parent while a submission
held the same names split into last / first / middle — two records of one fact,
in two shapes, kept in step by nobody. The parts won, because the agency forms
the office fills ask for them separately and a combined name cannot be split
back reliably.
"""
from django.test import Client, TestCase

from api.models import StudentProfile, User


class ProfileHoldsTheParentNamesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student',
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS', year_level=2)
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def _save(self, **fields):
        data = {
            'father_last_name': 'Dela Cruz', 'father_first_name': 'Juan',
            'father_middle_name': 'Ramirez',
            'mother_last_name': 'Santos', 'mother_first_name': 'Maria',
            'mother_middle_name': 'Reyes',
        }
        data.update(fields)
        self.c.post('/student/profile/', data)
        self.profile.refresh_from_db()
        return self.profile

    def test_the_profile_page_asks_for_the_parts_not_a_whole_name(self):
        html = self.c.get('/student/profile/').content.decode()
        for field in ('father_last_name', 'father_first_name', 'father_middle_name',
                      'mother_last_name', 'mother_first_name', 'mother_middle_name'):
            self.assertIn(f'name="{field}"', html)
        self.assertNotIn('name="father_name"', html)
        self.assertNotIn('name="mother_name"', html)

    def test_the_parts_are_saved(self):
        p = self._save()
        self.assertEqual(p.father_last_name, 'Dela Cruz')
        self.assertEqual(p.father_first_name, 'Juan')
        self.assertEqual(p.father_middle_name, 'Ramirez')
        self.assertEqual(p.mother_last_name, 'Santos')

    def test_the_combined_name_is_still_available_for_display(self):
        p = self._save()
        self.assertEqual(p.father_name, 'Juan R. Dela Cruz')
        self.assertEqual(p.mother_name, 'Maria R. Santos')

    def test_a_missing_middle_name_leaves_no_stray_initial(self):
        p = self._save(father_middle_name='')
        self.assertEqual(p.father_name, 'Juan Dela Cruz')

    def test_an_empty_parent_reads_as_empty_rather_than_whitespace(self):
        p = self._save(father_last_name='', father_first_name='', father_middle_name='')
        self.assertEqual(p.father_name, '')

    def test_the_combined_name_cannot_be_written_to(self):
        # It is derived. Anything that tries to set it is a bug worth failing on.
        with self.assertRaises(AttributeError):
            self.profile.father_name = 'Someone Else'
