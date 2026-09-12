"""An externally funded scholarship is not applied for in this system.

TDP, TES, GSIS, FHE and SUC-TDP are decided by UniFAST, CHED or GSIS. A student
applies to the agency, the agency grants the award, and the office receives the
awarded list afterwards — which reaches this system as a spreadsheet import, not
as a submission. Only the Academic Scholarship is applied for here; the BiPSU
Staff and Affirmative programmes have their own form in the staff portal.

That was already true of every page in the student portal, and untrue of two
things behind it:

* the recommendation card offered **Start Application** for any programme
  marked ``category='application'``, which is five external ones, and pointed
  them all at ``/student/apply/tdp/`` — a path with no route and no view;
* ``/api/student/applications/`` accepted any programme in the catalogue, and
  an Application created there is indistinguishable from a real award. It
  counts on the dashboard, prints on the masterlist and files in the archives.

The first was a dead button. The second was a live door, which is why the rule
lives on the serializer rather than in a template.
"""
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
    """The door that was actually open."""

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
        """Post an application the endpoint would otherwise accept.

        Application inherits TermStamped, so school_year and semester are
        required by `fields = '__all__'`; supplying them keeps a refusal here
        about the programme rather than about a missing column.
        """
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
        """The five the catalogue marks application-category and external."""
        for name, stype in (('Tulong Dunong', 'TDP'), ('GSIS Scholarship', 'GSIS'),
                            ('Free Higher Education', 'FHE'),
                            ('SUC Tulong Dunong', 'SUC-TDP')):
            with self.subTest(programme=stype):
                programme = self._programme(name, stype, 'external')
                self.assertEqual(self._submit(programme).status_code, 400)
        self.assertFalse(Application.objects.exists())

    def test_the_academic_scholarship_is_still_applied_for(self):
        """The rule has to remove one route, not the endpoint."""
        academic = self._programme('Academic Scholarship', 'Academic', 'internal')
        r = self._submit(academic)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Application.objects.get().scholarship, academic)

    def test_an_imported_award_on_an_external_programme_is_untouched(self):
        """The office's own records are the whole reason those programmes are
        in the catalogue. The rule refuses a submission, not an award."""
        tes = self._programme('Tertiary Education Subsidy', 'TES', 'external')
        award = Application.objects.create(
            student=self.profile, scholarship=tes, status='Approved')
        self.assertEqual(Application.objects.get(), award)
        body = self.c.get('/api/student/applications/').json()
        self.assertEqual([row['scholarship'] for row in body], [tes.pk])


class NoPageOffersToStartOneTest(TestCase):
    """The dead button, and that nothing points at the path it used.

    Checked against the template sources rather than a rendered page:
    student/recommendations.html has no route of its own, so a view test cannot
    reach it, and a link that 404s is exactly the kind of thing that survives
    unnoticed in a page nobody loads.
    """

    def test_no_template_links_to_the_tdp_application_form(self):
        """A link, not a mention: the card still explains in a comment why the
        button is gone, and naming the path there is the point of the note."""
        offenders = [os.path.basename(path) for path in template_files()
                     if 'apply/tdp/"' in open(path, encoding='utf-8').read()]
        self.assertEqual(offenders, [], 'still linking a route that does not exist')

    def test_the_path_is_not_routed(self):
        """It never was. This is here so that removing the link and quietly
        adding the view back would not both pass."""
        self.assertEqual(Client().get('/student/apply/tdp/').status_code, 404)

    def test_the_recommendation_card_offers_an_application_for_academic_only(self):
        source = next(path for path in template_files()
                      if path.endswith(os.path.join('student', 'recommendations.html')))
        body = open(source, encoding='utf-8').read()
        self.assertIn('/student/apply/academic/', body)
        # One Start Application button, and it is Academic's.
        self.assertEqual(body.count('Start Application'), 1)
        self.assertIn('Apply externally', body)
