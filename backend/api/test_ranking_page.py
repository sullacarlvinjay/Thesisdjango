"""Student Ranking is a report of what the eligibility rules say. Nothing more.

Nobody applies for Affirmative Action. Eligibility is decided from the student's
own profile by :meth:`AffirmativeRecommendation.evaluate_and_sync`, so the page
that used to carry an 'Applicants' tab beside the recommendations was ranking a
submission that cannot be made — and ranking it on columns no form has ever
written, so every applicant scored zero and rendered ineligible.

Endorsing and disqualifying by hand went with it. The award is recorded on the
Archives page like every other programme's, so a status set here was a second,
private answer to a question already written down somewhere the reports read.
What a recommendation says is now decided only by the rules — which still
disqualify a student themselves when one stops passing.
"""
from django.test import Client, TestCase

from api.models import (
    AffirmativeRecommendation, AffirmativeStaffApplication, StudentProfile, User,
)


class RankingPageTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.officer = User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='pw', role='vpsea', first_name='Ofelia', last_name='Reyes')
        self.client.force_login(self.officer)

    def a_student(self, email='ana@bipsu.edu.ph', student_id='2022-00111', **fields):
        user = User.objects.create_user(
            username=email, email=email, password='pw',
            first_name='Ana', last_name='Lim', role='student')
        return StudentProfile.objects.create(user=user, student_id=student_id, **fields)

    def an_eligible_student(self, **kw):
        """Passes all three rules, so evaluate_and_sync recommends them."""
        return self.a_student(shs_gpa=91.0, suc_exam_score=42.0, suc_exam_total=50.0,
                              is_tes_beneficiary=False, course='BSCS', **kw)

    # ── The applicant list is gone ──────────────────────────────────────────

    def test_the_page_renders_without_an_applicants_tab(self):
        self.an_eligible_student()
        page = self.client.get('/vpsea/ranking/').content.decode()
        self.assertNotIn('Applicant Rankings', page)
        self.assertNotIn('tab=applicants', page)
        self.assertIn('Rule-Based Recommendation', page)

    def test_an_affirmative_application_is_not_ranked_here(self):
        """A row of the old shape must not reappear on the page."""
        AffirmativeStaffApplication.objects.create(
            full_name='Juan Dela Cruz', email='juan@bipsu.edu.ph',
            qualified_for='Affirmative', status='Pending Validation',
            course='BS Biology', shs_gpa=95.0)
        page = self.client.get('/vpsea/ranking/').content.decode()
        self.assertNotIn('Juan Dela Cruz', page)

    def test_the_page_still_lists_a_student_the_rules_pass(self):
        self.an_eligible_student()
        page = self.client.get('/vpsea/ranking/').content.decode()
        self.assertIn('Lim', page)

    def test_the_api_returns_recommendations_and_no_applicants(self):
        """The DRF endpoint mirrors the page, so it lost the same half."""
        from rest_framework.authtoken.models import Token
        self.an_eligible_student()
        token, _ = Token.objects.get_or_create(user=self.officer)
        api = Client(HTTP_AUTHORIZATION=f'Token {token.key}')

        body = api.get('/api/vpsea/ranking/').json()
        self.assertNotIn('applicants', body)
        self.assertEqual(len(body['recommendations']), 1)

    # ── Endorsing is gone ───────────────────────────────────────────────────

    def test_no_endorse_control_is_offered(self):
        self.an_eligible_student()
        page = self.client.get('/vpsea/ranking/').content.decode()
        self.assertNotIn('Endorse', page)
        self.assertNotIn('value="endorse"', page)

    def test_posting_endorse_does_not_change_a_recommendation(self):
        """The action is not merely hidden — the view refuses to act on it."""
        self.an_eligible_student()
        self.client.get('/vpsea/ranking/')          # sync creates the row
        rec = AffirmativeRecommendation.objects.get()
        self.client.post('/vpsea/ranking/',
                         {'rec_id': rec.id, 'action': 'endorse'})
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'Recommended')

    def test_endorsed_is_no_longer_a_status_the_field_offers(self):
        choices = dict(AffirmativeRecommendation._meta.get_field('status').choices)
        self.assertNotIn('Endorsed', choices)
        self.assertIn('Recommended', choices)
        self.assertIn('Disqualified', choices)

    # ── What the page still does ────────────────────────────────────────────

    def test_no_disqualify_control_is_offered(self):
        self.an_eligible_student()
        page = self.client.get('/vpsea/ranking/').content.decode()
        self.assertNotIn('Disqualify', page)
        self.assertNotIn('value="disqualify"', page)

    def test_posting_disqualify_does_not_change_a_recommendation(self):
        """Nothing on this page is set by hand any more — only the rules decide."""
        self.an_eligible_student()
        self.client.get('/vpsea/ranking/')
        rec = AffirmativeRecommendation.objects.get()
        self.client.post('/vpsea/ranking/',
                         {'rec_id': rec.id, 'action': 'disqualify'})
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'Recommended')

    def test_re_evaluating_still_works(self):
        self.an_eligible_student()
        response = self.client.post('/vpsea/ranking/', {'action': 'resync'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AffirmativeRecommendation.objects.count(), 1)

    def test_raising_the_passing_threshold_disqualifies_a_student(self):
        """A recommendation is only created while the rules pass, so the student
        has to be picked up at a threshold they clear before one can drop them."""
        self.an_eligible_student()                   # SHS GPA 91
        self.client.get('/vpsea/ranking/?passing=75')
        self.assertEqual(AffirmativeRecommendation.objects.get().status, 'Recommended')

        self.client.get('/vpsea/ranking/?passing=95')
        self.assertEqual(AffirmativeRecommendation.objects.get().status, 'Disqualified')
