from types import SimpleNamespace

from django.test import SimpleTestCase

from api.tes_ranking import unanswered_on_record

VALID_SCHOOL = 'School of Technologies and Computer Studies'

BASELINE = dict(
    citizenship='Filipino',
    year_level=2,
    has_previous_degree=False,
    year_first_enrolled=2024,
    is_solo_parent_dependent=False,
    disability_type='NO',
    household_size=5,
    family_income=120000.0,
    school=VALID_SCHOOL,
    is_listahanan_household=False,
    is_4ps_beneficiary=False,
)


def profile(**overrides):
    return SimpleNamespace(**{**BASELINE, **overrides})


class BasisPathUnansweredOnRecord(SimpleTestCase):

    def test_p01_baseline_no_gaps(self):
        self.assertEqual(unanswered_on_record(profile()), ())

    def test_p02_loop_required_answer_is_none(self):
        self.assertIn('Citizenship', unanswered_on_record(profile(citizenship=None)))

    def test_p03_loop_required_answer_is_blank(self):
        self.assertIn('Citizenship', unanswered_on_record(profile(citizenship='')))

    def test_p04_loop_required_answer_is_whitespace(self):
        self.assertIn('Citizenship', unanswered_on_record(profile(citizenship='   ')))

    def test_p05_loop_non_string_value_is_kept(self):
        self.assertNotIn('Year level', unanswered_on_record(profile(year_level=2)))

    def test_p06_income_is_none_skips_positivity_check(self):
        gaps = unanswered_on_record(profile(family_income=None))
        self.assertEqual(gaps.count('Household income'), 1)

    def test_p07_income_zero_is_flagged(self):
        self.assertIn('Household income', unanswered_on_record(profile(family_income=0)))

    def test_p08_income_negative_is_flagged(self):
        self.assertIn('Household income', unanswered_on_record(profile(family_income=-1)))

    def test_p09_household_size_is_none_skips_positivity_check(self):
        gaps = unanswered_on_record(profile(household_size=None))
        self.assertEqual(gaps.count('Household size'), 1)

    def test_p10_household_size_zero_is_flagged(self):
        self.assertIn('Household size', unanswered_on_record(profile(household_size=0)))

    def test_p11_school_falsy_is_flagged_as_missing(self):
        self.assertIn('School', unanswered_on_record(profile(school=None)))

    def test_p12_school_blank_is_flagged_as_missing(self):
        self.assertIn('School', unanswered_on_record(profile(school='   ')))

    def test_p13_school_unrecognised_is_flagged_for_ched(self):
        gaps = unanswered_on_record(profile(school='Backyard State College'))
        self.assertIn('CHED recognition of "Backyard State College"', gaps)
        self.assertNotIn('School', gaps)

    def test_p14_both_listings_unknown_is_flagged(self):
        gaps = unanswered_on_record(
            profile(is_listahanan_household=None, is_4ps_beneficiary=None))
        self.assertIn('Listahanan / 4Ps listing', gaps)

    def test_p15_listahanan_unknown_but_4ps_known_is_accepted(self):
        gaps = unanswered_on_record(
            profile(is_listahanan_household=None, is_4ps_beneficiary=True))
        self.assertNotIn('Listahanan / 4Ps listing', gaps)

    def test_p16_gaps_are_deduplicated(self):
        gaps = unanswered_on_record(profile(family_income=None))
        self.assertEqual(len(gaps), len(set(gaps)))
