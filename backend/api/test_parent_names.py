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
        # Sex is here because the TES form refuses a profile without it — CHED
        # marks that column Required and the form reads it rather than asking.
        # These tests are about where the parents' names live, not that gate.
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS', year_level=2,
            middle_name='Reyes', gender='Female',
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

    def test_the_apply_form_fills_the_names_in_from_the_profile(self):
        """They are editable there now, but they still arrive already filled in."""
        r = self.c.get('/student/apply/tes/')
        html = r.content.decode()
        self.assertIn('Dela Cruz', html)
        self.assertIn('Santos', html)
        self.assertIn('Reyes', html)          # the student's own middle name
        self.assertEqual(r.context['post']['father_last_name'], 'Dela Cruz')
        self.assertEqual(r.context['post']['middle_name'], 'Reyes')

    def test_the_boxes_write_back_to_the_profile_not_onto_the_application(self):
        """The form posts the names, but the profile is where they land."""
        html = self.c.get('/student/apply/tes/').content.decode()
        self.assertIn('name="father_last_name"', html)
        self.assertIn('name="middle_name"', html)
        self.assertIn('saved back to it', html)

    def test_the_form_says_where_the_filled_in_values_come_from(self):
        # A bulk update has to name the table the columns are on — the profile's
        # proxies work on an instance, not on a queryset.
        FamilyBackground.objects.filter(student=self.profile).update(
            father_last_name='', mother_last_name='')
        html = self.c.get('/student/apply/tes/').content.decode()
        self.assertIn('My Profile', html)

    def test_submitting_stores_no_names_on_the_application(self):
        self.c.post('/student/apply/tes/', {
            'student_id': '2022-00111', 'last_name': 'Lim', 'first_name': 'Ana', 'gender': 'Female', 'year_level': '2',
            'mother_last_name': 'Santos', 'mother_first_name': 'Maria',
            'father_last_name': 'Dela Cruz', 'father_first_name': 'Juan',
            'father_middle_name': 'Ramirez', 'middle_name': 'Reyes',
            'lrn': '123456789012', 'birthdate': '2004-01-01',
            'complete_program': 'BACHELOR OF SCIENCE IN COMPUTER SCIENCE',
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
            'student_id': '2022-00111', 'last_name': 'Lim', 'first_name': 'Ana', 'gender': 'Female', 'year_level': '2',
            'mother_last_name': 'Santos', 'mother_first_name': 'Maria',
            'father_last_name': 'Dela Cruz', 'father_first_name': 'Juan',
            'father_middle_name': 'Ramirez', 'middle_name': 'Reyes',
            'lrn': '1', 'birthdate': '2004-01-01',
            'complete_program': 'BACHELOR OF SCIENCE IN COMPUTER SCIENCE',
            'is_solo_parent_dependent': '0'})
        FamilyBackground.objects.filter(student=self.profile).update(father_first_name='Juanito')
        tes = TESApplication.objects.get(student=self.profile)
        tes.refresh_from_db()
        self.assertEqual(tes.student.father_first_name, 'Juanito',
                         'the application still shows a stale copy of the name')
