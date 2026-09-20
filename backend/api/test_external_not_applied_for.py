import os

from django.conf import settings
from django.test import Client, TestCase
from rest_framework.authtoken.models import Token

from api.models import Application, Scholarship, StudentProfile, User


def template_files():
    for root in settings.TEMPLATES[0]['DIRS']:
        for folder, _, files in os.walk(root):
            for name in files:
                if name.endswith('.html'):
                    yield os.path.join(folder, name)


class TheApplicationApiRefusesAnExternalProgrammeTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student')
        self.profile = StudentProfile.objects.create(
            user=user, student_id='2022-00111', course='BSCS', year_level=3)
        token, _ = Token.objects.get_or_create(user=user)
        self.c = Client(HTTP_AUTHORIZATION=f'Token {token.key}')

    def _programme(self, name, stype, group):
        return Scholarship.objects.create(
            name=name, type=stype, group=group, category='application',
            description='x', eligibility='x', requirements=[])

    def _submit(self, programme):
        return self.c.post('/api/student/applications/', {
            'scholarship': programme.pk,
            'school_year': '2026-2027',
            'semester': '1st Semester',
        }, content_type='application/json')

    def test_an_external_programme_is_refused(self):
        tes = self._programme('Tertiary Education Subsidy', 'TES', 'external')
        r = self._submit(tes)
        self.assertEqual(r.status_code, 400)
        self.assertIn('applied for through the funding agency',
                      str(r.json()['scholarship']))
        self.assertFalse(Application.objects.exists(),
                         'an award nobody granted was written anyway')

    def test_every_externally_funded_programme_is_refused_not_just_tes(self):
        for name, stype in (('Tulong Dunong', 'TDP'), ('GSIS Scholarship', 'GSIS'),
                            ('Free Higher Education', 'FHE'),
                            ('SUC Tulong Dunong', 'SUC-TDP')):
            with self.subTest(programme=stype):
                programme = self._programme(name, stype, 'external')
                self.assertEqual(self._submit(programme).status_code, 400)
        self.assertFalse(Application.objects.exists())

    def test_the_academic_scholarship_is_still_applied_for(self):
        academic = self._programme('Academic Scholarship', 'Academic', 'internal')
        r = self._submit(academic)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Application.objects.get().scholarship, academic)

    def test_an_imported_award_on_an_external_programme_is_untouched(self):
        tes = self._programme('Tertiary Education Subsidy', 'TES', 'external')
        award = Application.objects.create(
            student=self.profile, scholarship=tes, status='Approved')
        self.assertEqual(Application.objects.get(), award)
        body = self.c.get('/api/student/applications/').json()
        self.assertEqual(
            [row['scholarship'] for row in body['results']], [tes.pk],
            'the list endpoint is paged, so the rows are under "results"')


class NoPageOffersToStartOneTest(TestCase):
    def test_no_template_links_to_the_tdp_application_form(self):
        offenders = [os.path.basename(path) for path in template_files()
                     if 'apply/tdp/"' in open(path, encoding='utf-8').read()]
        self.assertEqual(offenders, [], 'still linking a route that does not exist')

    def test_the_path_is_not_routed(self):
        self.assertEqual(Client().get('/student/apply/tdp/').status_code, 404)

    def test_the_recommendation_card_offers_an_application_for_academic_only(self):
        source = next(path for path in template_files()
                      if path.endswith(os.path.join('student', 'recommendations.html')))
        body = open(source, encoding='utf-8').read()
        self.assertIn('/student/apply/academic/', body)
        self.assertEqual(body.count('Start Application'), 1)
        self.assertIn('Apply externally', body)
