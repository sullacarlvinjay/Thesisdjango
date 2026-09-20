from pathlib import Path

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase

from api.models import ImportedScholar, Scholarship, SystemSettings, User

JS = settings.BASE_DIR / 'static' / 'js'


def template_files():
    for root in settings.TEMPLATES[0]['DIRS']:
        yield from Path(root).rglob('*.html')


class SomethingHasToActuallySubmitTest(SimpleTestCase):

    def templates_declaring_auto_submit(self):
        return [path for path in template_files()
                if 'data-auto-submit' in path.read_text(encoding='utf-8')]

    def test_the_marker_is_used_somewhere(self):
        self.assertTrue(self.templates_declaring_auto_submit(),
                        'nothing declares data-auto-submit; this test is stale')

    def test_the_script_that_implements_the_marker_does_submit_the_form(self):
        source = (JS / 'loading.js').read_text(encoding='utf-8')
        self.assertIn('data-auto-submit', source,
                      'loading.js is what makes the attribute mean anything')
        self.assertIn('form.submit()', source,
                      'marking a dropdown busy without submitting the form leaves '
                      'the page spinning and the figures unchanged')

    def test_only_one_script_submits_so_nothing_fires_twice(self):
        submitters = []
        for path in sorted(JS.glob('*.js')):
            source = path.read_text(encoding='utf-8')
            if 'data-auto-submit' in source and 'submit()' in source:
                submitters.append(path.name)
        self.assertEqual(
            submitters, ['loading.js'],
            f'more than one script submits data-auto-submit forms: {submitters}. '
            'Two of them on one page sends the request twice.')

    def test_a_form_already_submitting_is_not_submitted_again(self):
        source = (JS / 'loading.js').read_text(encoding='utf-8')
        self.assertIn("form.dataset.busy !== '1'", source)

    def test_an_inline_onchange_is_left_to_submit_itself(self):
        source = (JS / 'loading.js').read_text(encoding='utf-8')
        self.assertIn('if (ours && form.dataset.busy', source,
                      'the profile photo pickers submit through their own onchange; '
                      'loading.js must only show them as busy or they fire twice')


class TheFilterPagesLoadTheScriptTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def test_the_analytics_filters_have_something_to_submit_them(self):
        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn('data-auto-submit', html)
        self.assertIn('js/loading', html,
                      'the filter form is marked auto-submitting but the page loads '
                      'nothing that submits it')

    def test_the_retired_helper_is_gone_for_good(self):
        self.assertFalse((JS / 'auto-submit.js').exists(),
                         'two scripts submitting the same form double the request')
        for path in template_files():
            self.assertNotIn('auto-submit.js', path.read_text(encoding='utf-8'),
                             f'{path.name} still asks for a script that was removed')


class ChangingTheFiltersChangesTheFiguresTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        for stype in ('Academic', 'CHED', 'TDP'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype, category='application',
                description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

        for n in range(4):
            ImportedScholar.objects.create(
                scholarship_type='CHED', term_label='25-1', student_id=f'2022-1{n:04d}',
                last_name=f'Cruz{n}', first_name='Juan', course='BSCE', year_level=2)
        for n in range(2):
            ImportedScholar.objects.create(
                scholarship_type='CHED', term_label='25-2', student_id=f'2022-2{n:04d}',
                last_name=f'Reyes{n}', first_name='Ana', course='BSIT', year_level=2)
        ImportedScholar.objects.create(
            scholarship_type='TDP', term_label='25-1', student_id='2022-30000',
            last_name='Lim', first_name='Ben', course='BSED', year_level=3)

    def context(self, **params):
        response = self.c.get('/vpsea/analytics/', params)
        self.assertEqual(response.status_code, 200)
        return response.context

    def test_picking_another_semester_changes_the_counts(self):
        first = self.context(sy='25-1')
        second = self.context(sy='25-2')
        self.assertEqual(first['rollover_counts']['CHED'], 4)
        self.assertEqual(second['rollover_counts']['CHED'], 2)
        self.assertNotEqual(first['selected_sy_display'], second['selected_sy_display'])

    def test_picking_another_semester_changes_the_course_chart(self):
        self.assertEqual(
            [row['course'] for row in self.context(sy='25-1')['course_dist']],
            ['BSCE', 'BSED'])
        self.assertEqual(
            [row['course'] for row in self.context(sy='25-2')['course_dist']],
            ['BSIT'])

    def test_picking_a_program_narrows_the_figures_to_it(self):
        everything = self.context(sy='25-1')
        just_tdp = self.context(sy='25-1', stype='TDP')
        self.assertEqual([row['course'] for row in everything['course_dist']],
                         ['BSCE', 'BSED'])
        self.assertEqual([row['course'] for row in just_tdp['course_dist']], ['BSED'])
        self.assertEqual(just_tdp['selected_type'], 'TDP')

    def test_the_two_filters_work_together(self):
        narrowed = self.context(sy='25-2', stype='CHED')
        self.assertEqual([row['course'] for row in narrowed['course_dist']], ['BSIT'])
        self.assertEqual(narrowed['selected_type'], 'CHED')
        self.assertIn('2nd Semester', narrowed['selected_sy_display'])

    def test_the_selected_option_comes_back_marked_selected(self):
        html = self.c.get('/vpsea/analytics/', {'sy': '25-2', 'stype': 'CHED'}).content.decode()
        self.assertRegex(html, r'<option value="25-2"\s+selected>')
        self.assertRegex(html, r'<option value="CHED"\s+selected>')

    def test_a_cached_page_does_not_serve_one_selection_for_another(self):
        self.context(sy='25-1')
        again = self.context(sy='25-2')
        self.assertEqual(again['rollover_counts']['CHED'], 2,
                         'the cache key ignored the semester that was asked for')
