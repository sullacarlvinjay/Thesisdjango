from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import Scholarship, ScholarshipLinkRequest, SystemSettings
from api.fixtures_registration import a_declared_scholar

CATALOGUE = (
    ('Academic Scholarship', 'Academic'),
    ('Tertiary Education Subsidy', 'TES'),
    ('Free Higher Education (FHE)', 'FHE'),
    ('Staff Scholarship', 'Staff'),
    ('Affirmative Action', 'Affirmative'),
)


def a_proof(name='award.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 award', content_type='application/pdf')


def a_programme(name, stype, **extra):
    return Scholarship.objects.create(
        name=name, type=stype, category='application', description='x',
        eligibility='x', requirements=[], **extra)


class RegistrationOffersEveryLiveProgrammeTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        for name, stype in CATALOGUE:
            a_programme(name, stype)

    def offered(self):
        return dict(Client().get('/register/').context['scholarship_types'])

    def test_tes_is_on_the_dropdown(self):
        self.assertIn('TES', self.offered())

    def test_a_student_can_declare_holding_tes(self):
        r = Client().post('/register/', a_declared_scholar(
            scholarship_type='TES', proof_document=a_proof()))

        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            list(ScholarshipLinkRequest.objects.values_list('scholarship_type', flat=True)),
            ['TES'])

    def test_a_programme_the_office_adds_itself_is_offered(self):
        a_programme('Provincial Board Grant', 'Provincial')
        self.assertIn('Provincial', self.offered())

    def test_a_programme_the_office_switches_off_is_not_offered(self):
        Scholarship.objects.filter(type='TES').update(is_active=False)
        self.assertNotIn('TES', self.offered())

    def test_an_award_from_a_retired_programme_is_still_accepted(self):
        Scholarship.objects.filter(type='TES').update(is_active=False)

        r = Client().post('/register/', a_declared_scholar(
            scholarship_type='TES', proof_document=a_proof()))

        self.assertEqual(r.status_code, 302)
        self.assertTrue(ScholarshipLinkRequest.objects.filter(
            scholarship_type='TES').exists())

    def test_a_programme_nobody_has_heard_of_is_refused(self):
        r = Client().post('/register/', a_declared_scholar(
            scholarship_type='Invented', proof_document=a_proof()))

        self.assertContains(r, 'Say which scholarship you already hold')
        self.assertFalse(ScholarshipLinkRequest.objects.exists())

    def test_the_programmes_students_may_not_declare_cannot_be_posted_either(self):
        for stype in ('Affirmative', 'FHE'):
            with self.subTest(type=stype):
                r = Client().post('/register/', a_declared_scholar(
                    scholarship_type=stype, proof_document=a_proof()))

                self.assertContains(r, 'Say which scholarship you already hold')
                self.assertFalse(ScholarshipLinkRequest.objects.exists())

    def test_the_programmes_students_may_not_declare_stay_off(self):
        offered = self.offered()
        self.assertNotIn('Affirmative', offered)
        self.assertNotIn('FHE', offered)

    def test_the_staff_scholarship_is_offered_for_dependents(self):
        self.assertIn('Staff', self.offered())

    def test_each_option_is_named_the_way_the_catalogue_names_it(self):
        Scholarship.objects.filter(type='TES').update(name='TES (UniFAST)')
        self.assertEqual(self.offered()['TES'], 'TES (UniFAST)')

    def test_nothing_the_catalogue_does_not_carry_is_offered(self):
        self.assertEqual(set(self.offered()), {'Academic', 'TES', 'Staff'})


class AnEmptyCatalogueStillLetsSomeoneRegisterTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')

    def test_the_canonical_list_stands_in_for_an_unseeded_catalogue(self):
        offered = dict(Client().get('/register/').context['scholarship_types'])
        self.assertIn('Academic', offered)
        self.assertIn('TES', offered)
        self.assertNotIn('Affirmative', offered)

    def test_a_declaration_is_still_accepted(self):
        r = Client().post('/register/', a_declared_scholar(
            scholarship_type='TES', proof_document=a_proof()))

        self.assertEqual(r.status_code, 302)
        self.assertTrue(ScholarshipLinkRequest.objects.filter(
            scholarship_type='TES').exists())
