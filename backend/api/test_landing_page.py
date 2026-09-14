from django.conf import settings
from django.test import Client, TestCase

from api.models import Scholarship, SystemSettings
from api.templatetags.srms_text import sentence_case


class SentenceCaseTest(TestCase):
    def test_the_first_letter_is_capitalised(self):
        self.assertEqual(sentence_case('for BiPSU students only'),
                         'For BiPSU students only')

    def test_and_the_first_letter_of_every_later_sentence(self):
        self.assertEqual(sentence_case('one. two! three? four'),
                         'One. Two! Three? Four')

    def test_nothing_else_is_touched(self):
        self.assertEqual(
            sentence_case('the CHED grant. it is not TES, and not DOST either.'),
            'The CHED grant. It is not TES, and not DOST either.')

    def test_a_name_spelled_with_an_inner_capital_survives(self):
        self.assertEqual(sentence_case('BiPSU runs it. UniFAST does not.'),
                         'BiPSU runs it. UniFAST does not.')

    def test_leading_whitespace_does_not_hide_the_first_letter(self):
        self.assertEqual(sentence_case('\n  a grant'), '\n  A grant')

    def test_a_sentence_closed_by_a_quote_still_opens_the_next_one(self):
        self.assertEqual(sentence_case('he said "yes." then he left.'),
                         'He said "yes." Then he left.')

    def test_an_already_correct_line_is_left_exactly_as_it_is(self):
        line = 'Must NOT be a TES beneficiary.'
        self.assertEqual(sentence_case(line), line)

    def test_nothing_at_all_is_the_empty_string_rather_than_None(self):
        self.assertEqual(sentence_case(None), '')
        self.assertEqual(sentence_case(''), '')


class TheCardsTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.internal = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            group='internal',
            description='bipsu’s merit award. it covers tuition.',
            eligibility='x',
            eligibility_list=['a GWA of 1.50 or better',
                              'must be a regular student'],
            benefits=['full tuition for the semester'],
            background='approved by the board in 2019. still running.',
            requirements=[])
        self.external = Scholarship.objects.create(
            name='CHED Merit', type='CHED', category='recommendation',
            group='external', description='funded by CHED. applied for outside.',
            eligibility='x', requirements=[])
        self.html = Client().get('/').content.decode()

    def test_a_description_typed_lowercase_is_printed_sentence_cased(self):
        self.assertIn('Bipsu’s merit award. It covers tuition.', self.html)

    def test_an_acronym_in_one_is_left_alone(self):
        self.assertIn('Funded by CHED. Applied for outside.', self.html)

    def test_every_eligibility_line_gets_the_same_treatment(self):
        self.assertIn('A GWA of 1.50 or better', self.html)
        self.assertIn('Must be a regular student', self.html)

    def test_so_do_the_dialogs_background_and_benefits(self):
        self.assertIn('Approved by the board in 2019. Still running.', self.html)
        self.assertIn('Full tuition for the semester', self.html)


class TheJumpLinksTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')

    def _programme(self, name, group, **extra):
        return Scholarship.objects.create(
            name=name, group=group, type=extra.pop('type', name[:20]),
            category='application', description='x', eligibility='x',
            requirements=[], **extra)

    def _html(self):
        return Client().get('/').content.decode()

    def test_the_internal_list_gets_a_link_and_an_anchor_to_land_on(self):
        self._programme('Academic Scholarship', 'internal')
        html = self._html()
        self.assertIn('href="#internal"', html)
        self.assertIn('id="internal"', html)

    def test_so_does_the_external_one(self):
        self._programme('CHED Merit', 'external')
        html = self._html()
        self.assertIn('href="#external"', html)
        self.assertIn('id="external"', html)

    def test_the_links_are_named_in_full_even_where_the_word_is_hidden(self):
        self._programme('Academic Scholarship', 'internal')
        self._programme('CHED Merit', 'external')
        html = self._html()
        self.assertIn('aria-label="Internal Scholarships"', html)
        self.assertIn('aria-label="External Scholarships"', html)

    def test_a_list_that_is_empty_is_not_linked_to(self):
        self._programme('Academic Scholarship', 'internal')
        html = self._html()
        self.assertIn('href="#internal"', html)
        self.assertNotIn('href="#external"', html)

    def test_a_catalogue_with_neither_renders_no_links_at_all(self):
        self._programme('Staff Scholarship', 'institutional')
        html = self._html()
        self.assertNotIn('landing-jump', html)
        self.assertIn('Staff Scholarship', html)

    def test_nothing_scrolls_by_itself_any_more(self):
        self._programme('Academic Scholarship', 'internal')
        self.assertNotIn('landing-ticker', self._html())

        css = (settings.BASE_DIR / 'static' / 'css' / 'srms.css').read_text(encoding='utf-8')
        js = (settings.BASE_DIR / 'static' / 'js' / 'landing.js').read_text(encoding='utf-8')
        self.assertNotIn('landing-ticker', css)
        self.assertNotIn('landing-ticker', js)

    def test_an_inactive_programme_is_not_advertised(self):
        self._programme('Retired Grant', 'internal', is_active=False)
        self.assertNotIn('Retired Grant', self._html())
