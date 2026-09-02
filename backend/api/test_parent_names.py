"""Parent names live on the profile, in parts, and are entered exactly once.

StudentProfile used to hold one combined string per parent while TESApplication
held the same names split into last / first / middle — two records of one fact,
in two shapes, kept in step by nobody. The parts won, because CHED's TES form
asks for them separately and a combined name cannot be split back reliably.
"""
from django.test import Client, TestCase

from api.models import FamilyBackground, StudentProfile, TESApplication, User


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


class TESReadsTheNamesOffTheProfileTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student',
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS', year_level=2,
            middle_name='Reyes',
            father_last_name='Dela Cruz', father_first_name='Juan', father_middle_name='Ramirez',
            mother_last_name='Santos', mother_first_name='Maria', mother_middle_name='Cruz')
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def test_the_application_no_longer_carries_its_own_copies(self):
        for gone in ('middle_name', 'father_last_name', 'father_first_name',
                     'father_middle_name', 'mother_last_name', 'mother_first_name',
                     'mother_middle_name'):
            self.assertNotIn(gone, [f.name for f in TESApplication._meta.fields],
                             f'TESApplication still keeps a second copy of {gone}')

    def test_the_apply_form_shows_the_profile_names_without_asking_again(self):
        html = self.c.get('/student/apply/tes/').content.decode()
        self.assertIn('Dela Cruz', html)
        self.assertIn('Santos', html)
        self.assertIn('Reyes', html)          # the student's own middle name
        self.assertIn('Taken from your profile', html)
        # Nothing on the form posts a name back.
        self.assertNotIn('name="father_last_name"', html)
        self.assertNotIn('name="middle_name"', html)

    def test_the_form_says_so_when_the_profile_is_missing_the_names(self):
        # A bulk update has to name the table the columns are on — the profile's
        # proxies work on an instance, not on a queryset.
        FamilyBackground.objects.filter(student=self.profile).update(
            father_last_name='', mother_last_name='')
        html = self.c.get('/student/apply/tes/').content.decode()
        self.assertIn('add it in My Profile', html)

    def test_submitting_stores_no_names_on_the_application(self):
        self.c.post('/student/apply/tes/', {
            'lrn': '123456789012', 'birthdate': '2004-01-01',
            'complete_program': 'BS Computer Science',
            'street_barangay': 'Brgy. Larrazabal', 'city_municipality': 'Naval',
            'province': 'Biliran', 'region': 'VIII', 'zip_code': '6560',
            'contact_number': '09181234567', 'email_address': 'ana@bipsu.edu.ph',
            'is_solo_parent_dependent': '0', 'is_first_gen_college': '1',
        })
        tes = TESApplication.objects.get(student=self.profile)
        self.assertEqual(tes.lrn, '123456789012')
        # The names are reachable through the student, and only there.
        self.assertEqual(tes.student.father_name, 'Juan R. Dela Cruz')
        self.assertEqual(tes.student.middle_name, 'Reyes')

    def test_correcting_the_profile_corrects_the_application_view(self):
        self.c.post('/student/apply/tes/', {
            'lrn': '1', 'birthdate': '2004-01-01', 'complete_program': 'BSCS',
            'is_solo_parent_dependent': '0'})
        FamilyBackground.objects.filter(student=self.profile).update(father_first_name='Juanito')
        tes = TESApplication.objects.get(student=self.profile)
        tes.refresh_from_db()
        self.assertEqual(tes.student.father_first_name, 'Juanito',
                         'the application still shows a stale copy of the name')
