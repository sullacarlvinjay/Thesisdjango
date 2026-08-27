"""The GWA an applicant declares has to survive the application.

It used to be written only into Application.form_data, leaving StudentProfile.gwa
on its 0.0 default. The eligibility panel then showed a live classification next
to a stale 'GWA 0.0' and two rule badges that said Pass no matter what — because
0.0 clears every ceiling.
"""
from django.test import Client, TestCase

from api.constants import academic_classification
from api.models import Application, Scholarship, StudentProfile, User


class AcademicClassificationTest(TestCase):
    """One rule, used by the view and mirrored by the page."""

    def test_the_ceilings_match_what_the_page_prints(self):
        self.assertEqual(academic_classification(1.00), 'University Scholar')
        self.assertEqual(academic_classification(1.29), 'University Scholar')
        self.assertEqual(academic_classification(1.30), 'College Scholar')
        self.assertEqual(academic_classification(1.50), 'College Scholar')
        self.assertEqual(academic_classification(1.51), 'Not Eligible')

    def test_an_empty_gwa_is_not_a_perfect_one(self):
        # 0.0 clears every ceiling numerically, which used to crown a student
        # who had entered nothing at all University Scholar.
        self.assertEqual(academic_classification(0), '')
        self.assertEqual(academic_classification(0.0), '')
        self.assertEqual(academic_classification(None), '')


class DeclaredGWAReachesTheProfileTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student',
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS', year_level=2)
        Scholarship.objects.create(name='Academic Scholarship', type='Academic',
                                   category='Merit-Based')
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def _apply(self, **overrides):
        data = {'action': 'submit', 'gwa': '1.4', 'semester': '1st Semester',
                'school_year': '2025-2026'}
        data.update(overrides)
        return self.c.post('/student/apply/academic/', data)

    def test_the_profile_starts_at_the_zero_that_caused_this(self):
        self.assertEqual(self.profile.gwa, 0.0)

    def test_applying_saves_the_gwa_the_student_declared(self):
        self._apply(gwa='1.4')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.gwa, 1.4)

    def test_the_panel_then_reads_back_what_was_declared(self):
        self._apply(gwa='1.4')
        self.profile.refresh_from_db()
        self.assertEqual(academic_classification(self.profile.gwa), 'College Scholar')

    def test_a_junk_gwa_never_overwrites_a_real_one(self):
        self.profile.gwa = 1.2
        self.profile.save()
        for junk in ('', 'abc', '0', '9.9', '-1'):
            self._apply(gwa=junk)
            self.profile.refresh_from_db()
            self.assertEqual(self.profile.gwa, 1.2, f'{junk!r} overwrote a real GWA')
            Application.objects.all().delete()

    def test_the_application_still_keeps_its_own_copy_of_the_form(self):
        self._apply(gwa='1.4')
        app = Application.objects.get(student=self.profile)
        self.assertEqual(app.form_data['gwa'], '1.4')


class DraftingIsGoneTest(TestCase):
    """Saving a draft is replaced by the browser keeping what was typed."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            role='student',
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS', year_level=2)
        Scholarship.objects.create(name='Academic Scholarship', type='Academic',
                                   category='Merit-Based')
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def test_the_page_no_longer_offers_a_draft_button(self):
        html = self.c.get('/student/apply/academic/').content.decode()
        self.assertNotIn('value="draft"', html)
        self.assertIn('value="submit"', html)

    def test_the_form_opts_into_the_browser_side_cache(self):
        html = self.c.get('/student/apply/academic/').content.decode()
        self.assertIn('data-cache="apply-academic"', html)
        self.assertIn('form-cache.js', html)

    def test_a_posted_draft_action_is_submitted_anyway_not_parked(self):
        # Nothing renders this button any more, but a stale tab might still post
        # it — it must not create a half-finished row the office has to chase.
        self.c.post('/student/apply/academic/',
                    {'action': 'draft', 'gwa': '1.4', 'semester': '1st Semester'})
        app = Application.objects.get(student=self.profile)
        self.assertEqual(app.status, 'Pending Validation')

    def test_the_blocked_page_does_not_ship_a_broken_script(self):
        Application.objects.create(
            student=self.profile, scholarship=Scholarship.objects.first(),
            status='Pending Validation', form_data={})
        html = self.c.get('/student/apply/academic/').content.decode()
        # The GWA ceilings are not in a blocked page's context; rendering the
        # script anyway produced `const UNIVERSITY_MAX = ;`.
        self.assertNotIn('MAX = ;', html)
        self.assertNotIn('UNIVERSITY_MAX', html)
