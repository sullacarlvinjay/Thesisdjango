"""The analytics chart logic, one function at a time.

These paths existed before, inside ``_build_analytics_context``, where the
only way to reach them was to construct a whole request and read a rendered
dashboard. The function ran at cyclomatic complexity 101 and no independent
path through any single chart could be stated on its own. Extracted, each one
takes an input and returns an answer, which is what makes these cases
possible at all.
"""

from django.test import TestCase

from api import analytics_charts as charts


class BandingTest(TestCase):

    def test_each_band_claims_the_marks_up_to_its_ceiling(self):
        for mark, band in ((1.00, '1.00-1.25'), (1.25, '1.00-1.25'),
                           (1.26, '1.26-1.50'), (1.50, '1.26-1.50'),
                           (1.51, '1.51-1.75'), (1.75, '1.51-1.75'),
                           (1.76, '1.76-2.00'), (2.00, '1.76-2.00'),
                           (2.01, '2.01-2.50'), (2.50, '2.01-2.50')):
            with self.subTest(mark=mark):
                self.assertEqual(charts.band_for(mark), band)

    def test_a_mark_below_one_is_not_a_gwa_and_is_excluded(self):
        for mark in (0, 0.99, -1, None, ''):
            with self.subTest(mark=mark):
                self.assertIsNone(charts.band_for(mark))

    def test_a_mark_past_the_last_ceiling_falls_outside_every_band(self):
        self.assertIsNone(charts.band_for(2.51))
        self.assertIsNone(charts.band_for(5.0))

    def test_text_where_a_mark_was_expected_is_excluded_not_raised(self):
        self.assertIsNone(charts.band_for('not a number'))

    def test_banding_nothing_returns_none_so_the_chart_can_be_omitted(self):
        self.assertIsNone(charts.banded([]))
        self.assertIsNone(charts.banded([0, None, 'x']))

    def test_banding_one_mark_counts_it_and_zeroes_the_rest(self):
        buckets = charts.banded([1.4])
        self.assertEqual(buckets['1.26-1.50'], 1)
        self.assertEqual(sum(buckets.values()), 1)

    def test_banding_many_marks_counts_each_one(self):
        buckets = charts.banded([1.0, 1.2, 1.4, 2.4, 9.9])
        self.assertEqual(buckets['1.00-1.25'], 2)
        self.assertEqual(buckets['1.26-1.50'], 1)
        self.assertEqual(buckets['2.01-2.50'], 1)
        self.assertEqual(sum(buckets.values()), 4)

    def test_an_empty_band_set_carries_every_band_at_zero(self):
        empty = charts.empty_bands()
        self.assertEqual(set(empty), set(charts.GWA_BANDS))
        self.assertEqual(set(empty.values()), {0})


class IdentityTest(TestCase):

    def test_a_student_number_wins_over_the_name(self):
        self.assertEqual(charts.identity('2026-0001', 'Santos', 'Maria'),
                         'id:20260001')

    def test_the_same_number_written_differently_is_one_person(self):
        self.assertEqual(charts.identity('2026-0001', 'Santos', 'Maria'),
                         charts.identity('2026 0001', 'Cruz', 'Jose'))

    def test_a_name_is_used_where_there_is_no_number(self):
        self.assertEqual(charts.identity('', 'Santos', 'Maria'),
                         'name:SANTOS MARIA')

    def test_spacing_and_case_in_a_name_do_not_split_one_person_in_two(self):
        self.assertEqual(charts.identity('', '  santos ', 'MARIA'),
                         charts.identity(None, 'Santos', ' Maria '))

    def test_a_row_with_neither_has_no_identity_at_all(self):
        self.assertIsNone(charts.identity('', '', ''))
        self.assertIsNone(charts.identity(None, None, None))


class TierWordTest(TestCase):

    def test_the_tier_is_read_out_of_however_a_sheet_spelled_it(self):
        for text, tier in (('Full Merit', 'Full'), ('FULL', 'Full'),
                           ('Half Merit', 'Half'), ('partial scholar', 'Half'),
                           ('', ''), (None, ''), ('Grantee', '')):
            with self.subTest(text=text):
                self.assertEqual(charts.tier_word(text), tier)


class SubtypeTest(TestCase):

    def test_academic_splits_by_scholar_classification(self):
        self.assertEqual(
            charts.subtype('Academic', {'gwa': 1.1}), 'University Scholar')
        self.assertEqual(
            charts.subtype('Academic', {'gwa': 1.4}), 'College Scholar')

    def test_an_academic_scholar_outside_both_classes_gets_no_series(self):
        self.assertEqual(charts.subtype('Academic', {'gwa': 2.4}), '')

    def test_ched_splits_by_tier(self):
        self.assertEqual(charts.subtype('CHED', {'tier': 'Full'}), 'Full Merit')
        self.assertEqual(charts.subtype('CHED', {'tier': 'Half'}), 'Half Merit')
        self.assertEqual(charts.subtype('CHED', {'tier': ''}), '')

    def test_every_other_programme_is_a_single_series(self):
        self.assertEqual(charts.subtype('TDP', {'gwa': 1.1, 'tier': 'Full'}), '')

    def test_the_series_name_reads_as_the_programme_when_unsplit(self):
        self.assertEqual(charts.series_name('TDP', ''), 'TDP')
        self.assertIn('Full Merit', charts.series_name('CHED', 'Full Merit'))


class MergeTest(TestCase):

    def test_merging_nothing_gives_nothing(self):
        self.assertEqual(charts.merge_people([]), {})

    def test_one_term_passes_straight_through(self):
        people = {'id:1': {'course': 'BSCS', 'gwa': 1.2}}
        self.assertEqual(charts.merge_people([people]), people)

    def test_a_person_in_two_terms_is_counted_once(self):
        merged = charts.merge_people([
            {'id:1': {'course': 'BSCS', 'gwa': 1.2}},
            {'id:1': {'course': 'BSCS', 'gwa': 1.3}},
        ])
        self.assertEqual(len(merged), 1)

    def test_a_sparser_later_row_does_not_replace_a_fuller_earlier_one(self):
        merged = charts.merge_people([
            {'id:1': {'course': 'BSCS', 'gwa': 1.2}},
            {'id:1': {'course': '', 'gwa': None}},
        ])
        self.assertEqual(merged['id:1']['course'], 'BSCS')

    def test_a_fuller_later_row_does_replace_a_sparser_earlier_one(self):
        merged = charts.merge_people([
            {'id:1': {'course': '', 'gwa': None}},
            {'id:1': {'course': 'BSIT', 'gwa': 1.4}},
        ])
        self.assertEqual(merged['id:1']['course'], 'BSIT')

    def test_courses_are_counted_over_merged_people(self):
        counts = charts.count_courses({
            'id:1': {'course': 'BSCS'},
            'id:2': {'course': 'BSCS'},
            'id:3': {'course': ''},
        })
        self.assertEqual(counts['BSCS'], 2)
        self.assertEqual(counts[charts.UNKNOWN_COURSE], 1)


class SeriesTest(TestCase):

    def _trend(self, counts_per_term):
        """Trend rows in the shape the chart builder produces."""
        return [{'counts': dict(counts), 'per_type': dict(counts)}
                for counts in counts_per_term]

    def test_a_programme_with_no_split_keeps_its_own_name(self):
        trend = self._trend([{'TDP': 3}, {'TDP': 4}])
        charts.rename_unsplit_series(trend, ['TDP'])
        self.assertEqual(trend[0]['counts'], {'TDP': 3})

    def test_an_unsplit_total_beside_split_ones_is_renamed_not_double_counted(self):
        trend = self._trend([{'Academic': 2, 'Academic — University Scholar': 5}])
        charts.rename_unsplit_series(trend, ['Academic'])
        self.assertNotIn('Academic', trend[0]['counts'])
        self.assertEqual(trend[0]['counts']['Academic — Level not recorded'], 2)
        self.assertEqual(trend[0]['counts']['Academic — University Scholar'], 5)

    def test_a_series_that_is_zero_in_every_term_is_not_drawn(self):
        trend = self._trend([{'TDP': 0}, {'TDP': 0}])
        self.assertEqual(charts.series_for(trend, ['TDP']), [])

    def test_a_series_with_one_non_zero_term_is_drawn(self):
        trend = self._trend([{'TDP': 0}, {'TDP': 2}])
        self.assertEqual(charts.series_for(trend, ['TDP']), ['TDP'])

    def test_series_come_back_in_programme_order(self):
        trend = self._trend([{'Academic': 1, 'TDP': 1, 'CHED — Full Merit': 1}])
        self.assertEqual(
            charts.series_for(trend, ['Academic', 'CHED', 'TDP']),
            ['Academic', 'CHED — Full Merit', 'TDP'])

    def test_a_series_is_never_listed_twice(self):
        trend = self._trend([{'TDP': 1}, {'TDP': 2}])
        self.assertEqual(charts.series_for(trend, ['TDP', 'TDP']), ['TDP'])


class SortAndShapeTest(TestCase):

    def test_terms_sort_by_year_then_semester(self):
        labels = ['26-2', '25-1', '26-1', '25-2']
        self.assertEqual(sorted(labels, key=charts.label_sort_key),
                         ['25-1', '25-2', '26-1', '26-2'])

    def test_an_unparseable_term_sorts_first_rather_than_raising(self):
        self.assertEqual(charts.label_sort_key('whole year'), 0)
        self.assertEqual(charts.label_sort_key(''), 0)

    def test_a_number_is_read_out_of_anything_or_falls_back_to_zero(self):
        self.assertEqual(charts.as_number('1.5'), 1.5)
        self.assertEqual(charts.as_number(None), 0.0)
        self.assertEqual(charts.as_number('x'), 0.0)

    def test_the_commonest_course_is_charted_first(self):
        rows = charts.course_distribution({'BSCS': 2, 'BSIT': 9, 'BSED': 5})
        self.assertEqual([row['course'] for row in rows],
                         ['BSIT', 'BSED', 'BSCS'])

    def test_a_chart_is_tall_enough_for_its_bars_but_never_tiny(self):
        self.assertEqual(charts.course_chart_height([]), 420)
        self.assertGreater(charts.course_chart_height([{}] * 20), 420)
        self.assertEqual(charts.trend_chart_height([]), 420)
        self.assertGreater(charts.trend_chart_height([{}] * 20), 420)


class SheetReadingTest(TestCase):

    def test_a_missing_record_reads_as_no_data_rather_than_raising(self):
        self.assertEqual(charts.course_counts_from_sheet(None, 'CHED', '26-1'), {})
        self.assertIsNone(charts.gwa_from_sheet(None, '26-1'))
        self.assertEqual(charts.details_from_sheet(None, 'CHED', '26-1'), {})

    def test_a_record_with_no_file_reads_as_no_data(self):
        class Filed:
            """A filed import whose spreadsheet went missing."""
            excel_file = None

        self.assertEqual(
            charts.course_counts_from_sheet(Filed(), 'CHED', '26-1'), {})
        self.assertIsNone(charts.gwa_from_sheet(Filed(), '26-1'))
