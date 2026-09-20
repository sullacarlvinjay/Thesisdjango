"""What the registration form posts is what the ranking rules later read.

The registration form is the widest module boundary in the system: a flat
dictionary of strings crosses into ``StudentProfile`` and its detail rows, and
from there into the rules that decide money. Nothing type-checks that
crossing, so it is asserted here — value by value, in the units the rules use.

``api/fixtures_registration.py`` builds the payload these cases post. It was
called ``test_registration_payload.py`` and cited as data-flow evidence in
``docs/TESTING.md``; it contains no assertions and is a fixture builder, not
a test. This module is the evidence it was standing in for.
"""

from django.test import Client, TestCase

from api.fixtures_registration import a_declared_scholar, a_student
from api.models import StudentProfile, SystemSettings, User


class RegistrationDataFlowTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.posted = a_student()
        response = Client().post('/register/', self.posted)
        self.assertIn(response.status_code, (200, 302))
        self.profile = StudentProfile.objects.get(
            student_id=self.posted['student_id'])

    def test_the_account_is_created_pending_rather_than_usable(self):
        account = User.objects.get(email=self.posted['email'])
        self.assertEqual(account.verification_status, 'pending')
        self.assertFalse(account.can_sign_in)

    def test_the_name_reaches_the_account_not_only_the_profile(self):
        account = self.profile.user
        self.assertEqual(account.first_name, self.posted['first_name'])
        self.assertEqual(account.last_name, self.posted['last_name'])

    def test_the_posted_text_reaches_the_profile_unchanged(self):
        for field in ('course', 'birth_place', 'civil_status', 'gender',
                      'contact_number', 'barangay', 'municipality', 'province',
                      'elementary', 'highschool', 'last_school',
                      'citizenship', 'middle_name'):
            with self.subTest(field=field):
                self.assertEqual(getattr(self.profile, field),
                                 self.posted[field])

    def test_money_and_counts_arrive_as_numbers_not_as_the_posted_strings(self):
        self.assertEqual(self.profile.family_income,
                         float(self.posted['family_income']))
        self.assertEqual(self.profile.household_size,
                         int(self.posted['household_size']))
        self.assertEqual(self.profile.year_first_enrolled,
                         int(self.posted['year_first_enrolled']))
        self.assertEqual(self.profile.year_level,
                         int(self.posted['year_level']))

    def test_the_marks_the_ranking_reads_arrive_as_floats(self):
        self.assertEqual(self.profile.shs_gpa, float(self.posted['shs_gpa']))
        self.assertEqual(self.profile.suc_exam_score,
                         float(self.posted['suc_exam_score']))
        self.assertEqual(self.profile.suc_exam_total,
                         float(self.posted['suc_exam_total']))

    def test_a_yes_or_no_arrives_as_a_boolean_not_as_the_word(self):
        answers = {
            'is_listahanan_household': True,
            'is_4ps_beneficiary': False,
            'is_solo_parent_dependent': False,
            'has_previous_degree': False,
            'highschool_is_public': False,
            'is_from_depressed_area': False,
        }
        for field, expected in answers.items():
            with self.subTest(field=field):
                stored = getattr(self.profile, field)
                self.assertIs(stored, expected)
                self.assertNotIsInstance(stored, str)

    def test_a_question_a_declared_scholar_is_never_asked_stays_unknown(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        posted = a_declared_scholar(
            email='second@bipsu.edu.ph', student_id='2022-00998',
            scholarship_type='DOST')
        posted['proof_document'] = SimpleUploadedFile(
            'award.pdf', b'%PDF-1.4', content_type='application/pdf')
        self.assertEqual(Client().post('/register/', posted).status_code, 302)

        profile = StudentProfile.objects.get(student_id='2022-00998')
        for field in ('is_4ps_beneficiary', 'is_listahanan_household',
                      'has_previous_degree', 'is_solo_parent_dependent'):
            with self.subTest(field=field):
                self.assertIsNone(
                    getattr(profile, field),
                    'a question this applicant was never asked became a No, '
                    'which the ranking would read as an answer they gave')

    def test_the_school_is_derived_from_the_course_when_left_blank(self):
        from api.constants import school_for_course
        from api.views_auth import _registration_profile_fields

        fields = _registration_profile_fields(
            {'course': self.posted['course'], 'school': ''}, {}, 'NO')
        self.assertEqual(fields['school'],
                         school_for_course(self.posted['course']))
        self.assertTrue(fields['school'])

    def test_the_certificates_posted_are_the_files_stored(self):
        for field in ('shs_gpa_cert', 'suc_exam_cert'):
            with self.subTest(field=field):
                stored = getattr(self.profile, field)
                self.assertTrue(stored, f'{field} was posted but not stored')
                self.assertIn(field.replace('_cert', ''), stored.name)

    def test_the_exam_percentage_the_ranking_uses_follows_the_stored_marks(self):
        expected = round(float(self.posted['suc_exam_score'])
                         / float(self.posted['suc_exam_total']) * 100, 2)
        self.assertAlmostEqual(self.profile.suc_exam_percent, expected, places=1)

    def test_a_fully_answered_form_leaves_the_rules_nothing_unanswered(self):
        from api import tes_ranking

        self.assertEqual(
            list(tes_ranking.unanswered_on_record(self.profile)), [],
            'the form collected an answer the ranking cannot see')

    def test_the_stored_profile_is_what_the_tes_rules_read(self):
        from api import tes_ranking

        result = tes_ranking.evaluate(self.profile)
        self.assertTrue(result.rules)
        sources = ' '.join(rule.source or '' for rule in result.rules)
        self.assertIn('StudentProfile', sources)
