"""Who qualifies for what, and where that decision is made.

Affirmative Action is decided from the student's own profile by the rule-based
recommender. The BiPSU Staff Scholarship has no merit test at all — a regular
appointment is the whole rule.
"""
from django.test import Client, TestCase

from api.models import (
    AffirmativeStaffApplication, AffirmativeRecommendation, StudentProfile,
    SystemSettings, User,
)


class StaffQualificationTest(TestCase):
    """Regular appointment, and nothing else."""

    def _application(self, **kw):
        defaults = dict(
            full_name='Maria Santos', email='maria@bipsu.edu.ph',
            contact_number='09171234567', date_of_birth='1990-01-01',
            gender='F', course='BSIT', year_level=2,
            qualified_for='Staff', status='Pending Validation',
        )
        defaults.update(kw)
        return AffirmativeStaffApplication(**defaults)

    def test_a_regular_employee_qualifies(self):
        app = self._application(is_nsu_staff=True, employment_status='Regular')
        self.assertTrue(app.is_regular_staff)

    def test_contractual_and_part_time_do_not(self):
        for status in ('Contractual', 'Part-time', ''):
            app = self._application(is_nsu_staff=True, employment_status=status)
            self.assertFalse(app.is_regular_staff, status or 'blank')

    def test_a_dependent_qualifies_through_their_staff_parent(self):
        app = self._application(is_nsu_dependent=True, staff_employee_id='EMP-0042')
        self.assertTrue(app.is_regular_staff)

    def test_a_dependent_without_a_named_staff_member_does_not(self):
        app = self._application(is_nsu_dependent=True, staff_employee_id='')
        self.assertFalse(app.is_regular_staff)

    def test_nothing_academic_is_consulted(self):
        """A regular employee qualifies regardless of grades or TES status."""
        app = self._application(
            is_nsu_staff=True, employment_status='Regular',
            shs_gpa=10.0, suc_exam_score=0.0, is_tes_beneficiary=True,
            has_baccalaureate=True,
        )
        self.assertTrue(app.is_regular_staff)


class StaffApplyFormTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        self.user = User.objects.create_user(
            username='staff@bipsu.edu.ph', email='staff@bipsu.edu.ph',
            password='pw', first_name='Maria', last_name='Santos', role='nsu_staff',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='staff@bipsu.edu.ph', password='pw'))

    def _post(self, employment_status='Regular'):
        return self.c.post('/nsu-staff/apply/', {
            'first_name': 'Maria', 'last_name': 'Santos',
            'date_of_birth': '1990-01-01', 'gender': 'F', 'course': 'BSIT',
            'student_number': '32-1-000111',
            'employment_status': employment_status, 'designation': 'Teaching',
            'years_of_service': '5', 'date_of_regularization': '2019-06-01',
            'action': 'submit',
        })

    def test_a_non_regular_appointment_is_turned_away_with_a_reason(self):
        r = self._post('Contractual')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'open to regular employees')
        self.assertContains(r, 'Contractual')

    def test_part_time_is_turned_away_too(self):
        r = self._post('Part-time')
        self.assertContains(r, 'open to regular employees')

    def test_a_regular_employee_is_not_blocked_by_the_rule(self):
        r = self._post('Regular')
        self.assertNotContains(r, 'open to regular employees', status_code=r.status_code)


class AffirmativeQualificationTest(TestCase):
    """Decided from StudentProfile by the recommender, not by the application."""

    def _profile(self, sid, gpa, exam, tes=False):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph',
            password='pw', first_name='Test', last_name=sid, role='student',
        )
        return StudentProfile.objects.create(
            user=u, student_id=sid, course='BSCS', year_level=2,
            shs_gpa=gpa, suc_exam_score=exam, is_tes_beneficiary=tes,
        )

    def test_the_recommender_reads_the_students_own_profile(self):
        self._profile('2024-0001', 88.0, 72.0)             # passes
        self._profile('2024-0002', 70.0, 80.0)             # GPA below 75
        self._profile('2024-0003', 90.0, 40.0)             # exam below 50
        self._profile('2024-0004', 90.0, 80.0, tes=True)   # TES beneficiary

        created, _ = AffirmativeRecommendation.evaluate_and_sync()
        self.assertEqual(created, 1)
        rec = AffirmativeRecommendation.objects.get()
        self.assertEqual(rec.student.student_id, '2024-0001')
        self.assertEqual(rec.status, 'Recommended')

    def test_editing_the_profile_re_decides_it(self):
        p = self._profile('2024-0005', 88.0, 72.0)
        AffirmativeRecommendation.evaluate_and_sync()
        self.assertEqual(AffirmativeRecommendation.objects.count(), 1)

        # The student later turns out to be a TES beneficiary.
        p.is_tes_beneficiary = True
        p.save()
        _, disqualified = AffirmativeRecommendation.evaluate_and_sync()
        self.assertEqual(disqualified, 1)
        self.assertEqual(AffirmativeRecommendation.objects.get().status, 'Disqualified')

    def test_the_application_model_no_longer_decides_affirmative(self):
        """The old determine_qualification() duplicated these rules; it is gone."""
        self.assertFalse(hasattr(AffirmativeStaffApplication, 'determine_qualification'))
