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

    def test_an_empty_database_draws_no_charts_at_all(self):
        r = self.page()
        html = r.content.decode()
        for flag in ('show_program', 'show_gwa', 'show_trend'):
            self.assertFalse(r.context[flag], flag)
        for canvas in ('programChart', 'gwaChart', 'courseChart',
                       'trendChart'):
            self.assertNotIn(canvas, html, f'{canvas} drawn with nothing in it')

    def test_the_cards_are_still_there_and_say_why_they_are_empty(self):
        html = self.page().content.decode()
        self.assertIn('Scholars by Semester', html)
        self.assertIn('Scholars by Program', html)
        self.assertIn('No rollover data available for this selection.', html)
        self.assertNotIn('Scholars per Scholarship Program', html,
                         'that card was retired; its numbers are in the by-semester '
                         'chart, one series per programme')

    def test_no_png_button_is_offered_for_a_chart_that_was_not_drawn(self):
        self.assertNotIn('data-png=', self.page().content.decode())

    def test_one_scholar_is_enough_to_count_as_programme_data(self):
        self.award(1)
        r = self.page()
        self.assertTrue(r.context['show_program'])
        self.assertTrue(any(r.context['rollover_counts'].values()))
        self.assertNotIn('programChart', r.content.decode(),
                         'the per-programme chart was retired as a duplicate')

    def test_the_gwa_chart_waits_for_an_academic_scholar(self):
        self.award(1, 'TDP')
        self.assertFalse(self.page().context['show_gwa'],
                         'TDP scholars are not banded by GWA')
        self.award(2, 'Academic')
        self.assertTrue(self.page().context['show_gwa'])

    def test_filtering_to_a_non_academic_programme_builds_no_gwa_chart(self):
        self.award(1, 'Academic')
        self.award(2, 'TDP', course='BSIT')
        html = self.page(stype='TDP').content.decode()
        self.assertNotIn('gwaChart', html)
        self.assertIn('courseChart', html)

    def test_every_canvas_in_the_markup_is_one_the_script_builds(self):
        for params in ({}, {'stype': 'Academic'}, {'stype': 'TDP'},
                       {'stype': 'CHED'}):
            self.award(hash(str(params)) % 9000 + 100, 'Academic')
            html = self.page(**params).content.decode()
            for canvas in ('gwaChart',
                           'courseChart', 'trendChart'):
                drawn = f'id="{canvas}"' in html
                built = f"getElementById('{canvas}')" in html
                self.assertEqual(drawn, built,
                                 f'{canvas} with {params}: canvas={drawn} script={built}')

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
