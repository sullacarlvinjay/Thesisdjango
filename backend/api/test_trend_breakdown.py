from django.test import Client, TestCase

from api.models import ImportedScholar, Scholarship, SystemSettings, User


class ScholarsOverTimeBreakdownTest(TestCase):

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
        self.seq = 0

    def scholar(self, term, stype='Academic', gwa=1.2, tier='', course='BSCE'):
        self.seq += 1
        return ImportedScholar.objects.create(
            scholarship_type=stype, term_label=term,
            student_id=f'2022-{self.seq:05d}', last_name=f'Cruz{self.seq}',
            first_name='Juan', course=course, year_level=2, gwa=gwa,
            award_tier=tier)

    def series(self, **params):
        response = self.c.get('/vpsea/analytics/', params)
        self.assertEqual(response.status_code, 200)
        return {s['type']: s['counts'] for s in response.context['trend_series']}

    def test_academic_splits_into_university_and_college_scholars(self):
        self.scholar('25-1', gwa=1.10)
        self.scholar('25-1', gwa=1.25)
        self.scholar('25-1', gwa=1.40)
        self.scholar('25-2', gwa=1.45)
        series = self.series(sy='25-1', stype='Academic')
        self.assertEqual(sorted(series), ['Academic — College Scholar',
                                          'Academic — University Scholar'])
        self.assertEqual(sum(series['Academic — University Scholar']), 2)
        self.assertEqual(sum(series['Academic — College Scholar']), 2)

    def test_the_split_follows_the_gwa_thresholds(self):
        self.scholar('25-1', gwa=1.29)
        self.scholar('25-2', gwa=1.30)
        series = self.series(sy='25-1', stype='Academic')
        self.assertEqual(sum(series['Academic — University Scholar']), 1)
        self.assertEqual(sum(series['Academic — College Scholar']), 1)

    def test_ched_splits_into_full_and_half_merit(self):
        self.scholar('25-1', stype='CHED', tier='Full')
        self.scholar('25-1', stype='CHED', tier='Full')
        self.scholar('25-2', stype='CHED', tier='Half')
        series = self.series(sy='25-1', stype='CHED')
        self.assertEqual(sorted(series), ['CHED — Full Merit', 'CHED — Half Merit'])
        self.assertEqual(sum(series['CHED — Full Merit']), 2)
        self.assertEqual(sum(series['CHED — Half Merit']), 1)

    def test_a_programme_with_no_sub_types_stays_one_series(self):
        self.scholar('25-1', stype='TDP')
        self.scholar('25-2', stype='TDP')
        self.assertEqual(sorted(self.series(sy='25-1', stype='TDP')), ['TDP'])

    def test_an_academic_scholar_with_no_gwa_is_not_forced_into_a_band(self):
        self.scholar('25-1', gwa=0)
        self.scholar('25-2', gwa=0)
        self.assertEqual(sorted(self.series(sy='25-1', stype='Academic')), ['Academic'])

    def test_the_unbanded_ones_are_named_apart_from_the_banded_ones(self):
        self.scholar('25-1', gwa=1.10)
        self.scholar('25-1', gwa=0)
        names = sorted(self.series(sy='25-1', stype='Academic'))
        self.assertEqual(names, ['Academic — Level not recorded',
                                 'Academic — University Scholar'])
        self.assertNotIn('Academic', names,
                         'a bare programme name beside its own levels reads as a total')

    def test_all_programmes_together_still_break_down(self):
        self.scholar('25-1', gwa=1.10)
        self.scholar('25-1', stype='CHED', tier='Half')
        self.scholar('25-2', stype='TDP')
        names = sorted(self.series(sy='25-1'))
        self.assertIn('Academic — University Scholar', names)
        self.assertIn('CHED — Half Merit', names)
        self.assertIn('TDP', names)


class ScholarsOverTimeFollowsThePeriodTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        Scholarship.objects.create(
            name='TDP Scholarship', type='TDP', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))
        self.seq = 0

    def scholar(self, term):
        self.seq += 1
        return ImportedScholar.objects.create(
            scholarship_type='TDP', term_label=term,
            student_id=f'2022-{self.seq:05d}', last_name=f'Lim{self.seq}',
            first_name='Ana', course='BSIT', year_level=2)

    def context(self, **params):
        response = self.c.get('/vpsea/analytics/', params)
        self.assertEqual(response.status_code, 200)
        return response.context

    def spread(self):
        for term in ('24-1', '24-2', '25-1', '25-2'):
            self.scholar(term)

    def test_the_server_sends_every_semester_so_the_toggle_can_slice(self):
        self.spread()
        labels = [d['label'] for d in self.context(sy='25-Y')['trend_data']]
        self.assertEqual(labels, ['24-1', '24-2', '25-1', '25-2', '26-1'],
                         'the active term is always on the list')

    def test_the_semesters_of_the_chosen_year_are_marked(self):
        self.spread()
        self.assertEqual(self.context(sy='25-Y')['trend_year_labels'], ['25-1', '25-2'])
        self.assertEqual(self.context(sy='24-2')['trend_year_labels'], ['24-1', '24-2'])

    def test_picking_another_year_marks_a_different_slice(self):
        self.spread()
        self.assertNotEqual(self.context(sy='24-1')['trend_year_labels'],
                            self.context(sy='25-1')['trend_year_labels'])

    def test_a_year_with_one_semester_marks_just_that_one(self):
        self.spread()
        self.assertEqual(self.context(sy='26-1')['trend_year_labels'], ['26-1'])

    def test_a_single_semester_period_offers_a_single_semester_range(self):
        self.spread()
        html = self.c.get('/vpsea/analytics/', {'sy': '25-1'}).content.decode()
        self.assertIn("{ value: 'term', label: 'This semester' }", html)
        self.assertIn('const TREND_ONE_TERM = true', html)

    def test_a_whole_year_period_has_no_single_semester_to_offer(self):
        self.spread()
        html = self.c.get('/vpsea/analytics/', {'sy': '25-Y'}).content.decode()
        self.assertIn('const TREND_ONE_TERM = false', html)

    def test_the_semester_range_marks_only_the_chosen_term(self):
        self.spread()
        html = self.c.get('/vpsea/analytics/', {'sy': '25-1'}).content.decode()
        flags = html.split('const trendInTerm = [')[1].split(']')[0]
        self.assertEqual(flags, 'false,false,true,false,false')

    def test_the_whole_year_marks_both_of_its_semesters(self):
        self.spread()
        html = self.c.get('/vpsea/analytics/', {'sy': '25-Y'}).content.decode()
        flags = html.split('const trendInTerm = [')[1].split(']')[0]
        self.assertEqual(flags, 'false,false,true,true,false')

    def test_the_term_name_does_not_carry_a_second_dash(self):
        self.spread()
        context = self.context(sy='25-1')
        self.assertEqual(context['selected_term_display'], '2025-2026 1st Semester')
        self.assertEqual(context['selected_sy_display'], '2025-2026 — 1st Semester')

    def test_the_chart_opens_on_whatever_the_period_named(self):
        self.spread()
        self.assertIn('buildTrendChart(TREND_RANGES[0].value)',
                      self.c.get('/vpsea/analytics/', {'sy': '25-1'}).content.decode())

    def test_the_chart_offers_both_ranges_and_opens_on_this_year(self):
        self.spread()
        html = self.c.get('/vpsea/analytics/', {'sy': '25-Y'}).content.decode()
        self.assertIn("{ value: 'year', label: 'This academic year' }", html)
        self.assertIn("{ value: 'all', label: 'All academic years' }", html)
        self.assertIn('buildTrendChart(TREND_RANGES[0].value)', html,
                      'it should open on whatever the period named')

    def test_the_marks_line_up_with_the_semesters_they_describe(self):
        self.spread()
        html = self.c.get('/vpsea/analytics/', {'sy': '25-Y'}).content.decode()
        flags = html.split('const trendInYear = [')[1].split(']')[0]
        self.assertEqual(flags, 'false,false,true,true,false')

    def test_the_card_is_named_for_what_it_actually_shows(self):
        self.spread()
        html = self.c.get('/vpsea/analytics/', {'sy': '25-Y'}).content.decode()
        self.assertIn('Scholars by Semester', html)
        self.assertNotIn('Scholars Over Time', html,
                         'the old name said nothing about semesters')
        self.assertIn('data-png-name="scholars-by-semester"', html)

    def test_the_name_carries_the_period_and_the_programme(self):
        self.spread()
        html = self.c.get('/vpsea/analytics/',
                          {'sy': '25-Y', 'stype': 'TDP'}).content.decode()
        self.assertIn('data-trend-scope', html)
        self.assertIn("const TREND_PROGRAM = 'TDP'", html)
        self.assertIn('const TREND_YEAR = ', html)
        self.assertIn("' by Semester — ' + scope", html)
        self.assertEqual(
            self.context(sy='25-Y', stype='TDP')['selected_academic_year'],
            '2025-2026',
            'the year the title is built from comes from the context, not the '
            'escaped copy escapejs leaves in the page')

    def test_the_caption_names_the_academic_year(self):
        self.spread()
        context = self.context(sy='25-Y')
        self.assertEqual(context['selected_academic_year'], '2025-2026')
        self.assertIn('data-trend-range',
                      self.c.get('/vpsea/analytics/', {'sy': '25-Y'}).content.decode())

    def test_all_academic_years_is_the_whole_history_in_one_chart(self):
        self.spread()
        labels = [d['label'] for d in self.context(sy='25-Y')['trend_data']]
        self.assertIn('24-1', labels)
        self.assertIn('25-2', labels)


class NoLineChartsAnywhereTest(TestCase):

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

    def test_no_chart_toggle_offers_a_line(self):
        import re
        html = self.c.get('/vpsea/analytics/').content.decode()
        for offered in re.findall(r'makeToggle\([^)]*?\[([^\]]*)\]', html):
            self.assertNotIn('line', offered.lower(),
                             f'a toggle still offers a line chart: [{offered}]')

    def test_a_single_choice_toggle_is_hidden_rather_than_shown_alone(self):
        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn('if (types.length < 2)', html,
                      'one lonely tab is worse than no tabs')
