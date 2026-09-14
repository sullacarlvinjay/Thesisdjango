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
        return self.a_student(shs_gpa=91.0, suc_exam_score=42.0, suc_exam_total=50.0,
                              is_tes_beneficiary=False, course='BSCS', **kw)

    def test_the_page_renders_without_an_applicants_tab(self):
        self.an_eligible_student()
        page = self.client.get('/vpsea/ranking/').content.decode()
        self.assertNotIn('Applicant Rankings', page)
        self.assertNotIn('tab=applicants', page)
        self.assertIn('Rule-Based Recommendation', page)

    def test_an_affirmative_application_is_not_ranked_here(self):
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
        from rest_framework.authtoken.models import Token
        self.an_eligible_student()
        token, _ = Token.objects.get_or_create(user=self.officer)
        api = Client(HTTP_AUTHORIZATION=f'Token {token.key}')

        body = api.get('/api/vpsea/ranking/').json()
        self.assertNotIn('applicants', body)
        self.assertEqual(len(body['recommendations']), 1)

    def test_no_endorse_control_is_offered(self):
        self.an_eligible_student()
        page = self.client.get('/vpsea/ranking/').content.decode()
        self.assertNotIn('Endorse', page)
        self.assertNotIn('value="endorse"', page)

    def test_posting_endorse_does_not_change_a_recommendation(self):
        self.an_eligible_student()
        self.client.get('/vpsea/ranking/')
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

    def test_no_disqualify_control_is_offered(self):
        self.an_eligible_student()
        page = self.client.get('/vpsea/ranking/').content.decode()
        self.assertNotIn('Disqualify', page)
        self.assertNotIn('value="disqualify"', page)

    def test_posting_disqualify_does_not_change_a_recommendation(self):
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
        self.an_eligible_student()
        self.client.get('/vpsea/ranking/?passing=75')
        self.assertEqual(AffirmativeRecommendation.objects.get().status, 'Recommended')

        self.client.get('/vpsea/ranking/?passing=95')
        self.assertEqual(AffirmativeRecommendation.objects.get().status, 'Disqualified')
