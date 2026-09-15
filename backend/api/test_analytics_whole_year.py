from django.test import Client, TestCase

from api.models import ImportedScholar, Scholarship, SystemSettings, User


class WholeAcademicYearTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        for stype in ('Academic', 'CHED'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype, category='application',
                description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def scholar(self, term, student_id, last='Cruz', first='Juan',
                course='BSCE', gwa=1.2, stype='CHED'):
        return ImportedScholar.objects.create(
            scholarship_type=stype, term_label=term, student_id=student_id,
            last_name=last, first_name=first, course=course, gwa=gwa, year_level=2)

    def page(self, **params):
        response = self.c.get('/vpsea/analytics/', params)
        self.assertEqual(response.status_code, 200)
        return response

    def test_a_year_with_one_semester_on_record_offers_no_whole_year_option(self):
        self.scholar('25-1', '2022-00001')
        groups = {g['sy']: [lbl for lbl, _ in g['options']]
                  for g in self.page().context['sy_groups']}
        self.assertIn('2025-2026', groups)
        self.assertNotIn('25-Y', groups['2025-2026'],
                         'there is only one semester, so a whole year is the same thing')

    def test_a_year_with_both_semesters_offers_the_whole_year(self):
        self.scholar('25-1', '2022-00001')
        self.scholar('25-2', '2022-00001')
        groups = {g['sy']: dict(g['options']) for g in self.page().context['sy_groups']}
        self.assertEqual(groups['2025-2026']['25-Y'], 'Whole academic year')
        self.assertEqual(groups['2025-2026']['25-1'], '1st Semester')
        self.assertEqual(groups['2025-2026']['25-2'], '2nd Semester')

    def test_the_whole_year_is_the_two_semesters_together(self):
        self.scholar('25-1', '2022-00001', last='Cruz', first='Juan')
        self.scholar('25-2', '2022-00002', last='Reyes', first='Ana')
        context = self.page(sy='25-Y').context
        self.assertTrue(context['whole_year'])
        self.assertEqual(sorted(context['term_labels']), ['25-1', '25-2'])
        self.assertEqual(context['rollover_counts']['CHED'], 2)

    def test_a_scholar_on_both_semesters_is_one_person_not_two(self):
        self.scholar('25-1', '2022-00001')
        self.scholar('25-2', '2022-00001')
        self.assertEqual(self.page(sy='25-1').context['rollover_counts']['CHED'], 1)
        self.assertEqual(self.page(sy='25-2').context['rollover_counts']['CHED'], 1)
        self.assertEqual(
            self.page(sy='25-Y').context['rollover_counts']['CHED'], 1,
            'the same student across two semesters is still one scholar')

    def test_the_course_chart_counts_that_person_once_too(self):
        self.scholar('25-1', '2022-00001', course='BSCE')
        self.scholar('25-2', '2022-00001', course='BSCE')
        self.scholar('25-1', '2022-00002', last='Reyes', first='Ana', course='BSIT')
        courses = {row['course']: row['scholars']
                   for row in self.page(sy='25-Y').context['course_dist']}
        self.assertEqual(courses, {'BSCE': 1, 'BSIT': 1})

    def test_a_scholar_who_changed_course_is_counted_under_the_later_one(self):
        self.scholar('25-1', '2022-00001', course='BSCE')
        self.scholar('25-2', '2022-00001', course='BSIT')
        courses = {row['course']: row['scholars']
                   for row in self.page(sy='25-Y').context['course_dist']}
        self.assertEqual(courses, {'BSIT': 1})

    def test_the_gwa_bands_read_the_whole_year_as_well(self):
        self.scholar('25-1', '2022-00001', gwa=1.1, stype='Academic')
        self.scholar('25-2', '2022-00001', gwa=1.1, stype='Academic')
        self.scholar('25-2', '2022-00002', last='Reyes', first='Ana',
                     gwa=1.6, stype='Academic')
        bands = {row['range']: row['count']
                 for row in self.page(sy='25-Y').context['gpa_ranges']}
        self.assertEqual(bands['1.00-1.25'], 1)
        self.assertEqual(bands['1.51-1.75'], 1)

    def test_the_page_says_which_period_it_is_showing(self):
        self.scholar('25-1', '2022-00001')
        self.scholar('25-2', '2022-00002', last='Reyes', first='Ana')
        html = self.page(sy='25-Y').content.decode()
        self.assertIn('2025-2026 — Whole academic year', html)

    def test_a_period_nobody_has_records_for_falls_back_to_the_active_term(self):
        self.scholar('25-1', '2022-00001')
        context = self.page(sy='99-Y').context
        self.assertEqual(context['selected_sy'], '26-1')
        self.assertFalse(context['whole_year'])

    def test_the_trend_still_walks_the_individual_semesters(self):
        self.scholar('25-1', '2022-00001')
        self.scholar('25-2', '2022-00002', last='Reyes', first='Ana')
        labels = [d['label'] for d in self.page(sy='25-Y').context['trend_data']]
        self.assertIn('25-1', labels)
        self.assertIn('25-2', labels)
        self.assertNotIn('25-Y', labels,
                         'a made-up whole-year term must never reach the trend')
