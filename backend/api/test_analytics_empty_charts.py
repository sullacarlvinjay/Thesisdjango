"""A chart with nothing in it is not drawn.

Chart.js given an empty dataset does not render blank — it renders a labelled,
gridded, entirely empty plot, which reads as a chart that failed rather than a
list nobody is on. Each card asks first whether it has anything to show and
says so in words when it does not.

The flags are resolved once in the view because the markup and the script both
need the same answer. They did not always agree: the GWA canvas was rendered
only for All Programmes or Academic, while the script built a GWA chart
whenever the bands existed at all. Filtering to any other programme therefore
handed Chart.js a null canvas, and the throw took out every chart built after
it in the same <script> — School, Course and Scholars Over Time all vanished.
"""
from django.test import Client, TestCase

from api.models import (
    Application, ImportedScholar, Scholarship, StudentProfile, SystemSettings,
    User,
)


class EmptyChartsTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        for stype in ('Academic', 'TDP', 'CHED'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype, category='application',
                description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def award(self, n, stype='Academic', course='BSCE', gwa=1.2):
        user = User.objects.create_user(
            username=f's{n}@bipsu.edu.ph', email=f's{n}@bipsu.edu.ph',
            password='pw', first_name=f'S{n}', last_name=f'Lim{n}', role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id=f'2022-{n:05d}', course=course, year_level=2,
            gwa=gwa)
        return Application.objects.create(
            student=profile, scholarship=Scholarship.objects.get(type=stype),
            status='Approved')

    def page(self, **params):
        r = self.c.get('/vpsea/analytics/', params)
        self.assertEqual(r.status_code, 200)
        return r

    # ── nothing on record at all ────────────────────────────────────────────

    def test_an_empty_database_draws_no_charts_at_all(self):
        r = self.page()
        html = r.content.decode()
        for flag in ('show_program', 'show_gwa', 'show_trend'):
            self.assertFalse(r.context[flag], flag)
        for canvas in ('programChart', 'gwaChart', 'schoolChart', 'courseChart',
                       'trendChart'):
            self.assertNotIn(canvas, html, f'{canvas} drawn with nothing in it')

    def test_the_cards_are_still_there_and_say_why_they_are_empty(self):
        html = self.page().content.decode()
        self.assertIn('Scholars per Scholarship Program', html)
        self.assertIn('No scholars on record for this selection.', html)

    def test_no_png_button_is_offered_for_a_chart_that_was_not_drawn(self):
        # data-png rather than the class: the class also names the delegated
        # click handler, which is rendered whether or not a button exists.
        self.assertNotIn('data-png=', self.page().content.decode())

    # ── something on record ─────────────────────────────────────────────────

    def test_one_scholar_is_enough_to_draw_the_programme_chart(self):
        self.award(1)
        r = self.page()
        self.assertTrue(r.context['show_program'])
        self.assertIn('programChart', r.content.decode())

    def test_the_gwa_chart_waits_for_an_academic_scholar(self):
        self.award(1, 'TDP')
        self.assertFalse(self.page().context['show_gwa'],
                         'TDP scholars are not banded by GWA')
        self.award(2, 'Academic')
        self.assertTrue(self.page().context['show_gwa'])

    # ── the canvas and the script agree ─────────────────────────────────────

    def test_filtering_to_a_non_academic_programme_builds_no_gwa_chart(self):
        """The mismatch that used to take the rest of the page down with it."""
        self.award(1, 'Academic')
        self.award(2, 'TDP', course='BSIT')
        html = self.page(stype='TDP').content.decode()
        self.assertNotIn('gwaChart', html)
        # …and the charts that came after it in the script are still built.
        self.assertIn('schoolChart', html)
        self.assertIn('courseChart', html)

    def test_every_canvas_in_the_markup_is_one_the_script_builds(self):
        for params in ({}, {'stype': 'Academic'}, {'stype': 'TDP'},
                       {'stype': 'CHED'}):
            self.award(hash(str(params)) % 9000 + 100, 'Academic')
            html = self.page(**params).content.decode()
            for canvas in ('programChart', 'gwaChart', 'schoolChart',
                           'courseChart', 'trendChart'):
                drawn = f'id="{canvas}"' in html
                built = f"getElementById('{canvas}')" in html
                self.assertEqual(drawn, built,
                                 f'{canvas} with {params}: canvas={drawn} script={built}')

    # ── the trend ───────────────────────────────────────────────────────────

    def test_two_empty_semesters_are_not_a_trend(self):
        ImportedScholar.objects.create(
            scholarship_type='CHED', term_label='25-2', last_name='Cruz',
            first_name='Juan', course='BSCE', year_level=2)
        r = self.page(stype='TDP')
        self.assertGreater(len(r.context['trend_data']), 1,
                           'two semesters exist, they are just empty for TDP')
        self.assertFalse(r.context['show_trend'])
        self.assertNotIn('trendChart', r.content.decode())

    def test_a_semester_with_scholars_does_draw_the_trend(self):
        ImportedScholar.objects.create(
            scholarship_type='CHED', term_label='25-2', last_name='Cruz',
            first_name='Juan', course='BSCE', year_level=2)
        r = self.page()
        self.assertTrue(r.context['show_trend'])
        self.assertIn('trendChart', r.content.decode())
