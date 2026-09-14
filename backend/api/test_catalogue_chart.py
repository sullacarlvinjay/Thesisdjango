from django.test import Client, TestCase

from api import catalogue
from api.constants import SCHOLARSHIP_LOGOS, SCHOLARSHIP_TYPE_CHOICES
from api.models import Scholarship, SystemSettings
from api.student_views import can_hold_alongside

BY_TYPE = {row['type']: row for row in catalogue.SCHOLARSHIPS}
DECLARABLE = {value for value, _ in SCHOLARSHIP_TYPE_CHOICES}


class ChartProgrammesTest(TestCase):
    def test_the_chart_programmes_are_all_in_the_catalogue(self):
        for type_ in ('FHE', 'SUC-TDP', 'JLSS'):
            with self.subTest(type=type_):
                self.assertIn(type_, BY_TYPE)

    def test_the_dost_entry_covers_both_of_its_tracks(self):
        entry = BY_TYPE['DOST']
        listed = ' '.join(entry['eligibility_list'])
        self.assertIn('RA 7687', listed)
        self.assertIn('Merit', listed)

    def test_the_dost_lookup_key_is_unchanged(self):
        self.assertEqual(BY_TYPE['DOST']['type'], 'DOST')

    def test_no_tier_column_was_invented_for_dost(self):
        from api.models import ScholarshipLinkRequest

        tiers = dict(ScholarshipLinkRequest._meta.get_field('award_tier').choices or [])
        self.assertNotIn('RA 7687', tiers)
        self.assertNotIn('Merit', tiers)

    def test_each_new_programme_is_filed_under_its_funder(self):
        for type_ in ('FHE', 'SUC-TDP', 'JLSS'):
            with self.subTest(type=type_):
                self.assertEqual(BY_TYPE[type_]['group'], 'external')

    def test_each_new_programme_wears_its_funders_seal(self):
        for type_, expected in (('FHE', 'UniFAST.png'),
                                ('SUC-TDP', 'UniFAST.png'),
                                ('JLSS', 'DOST.png')):
            with self.subTest(type=type_):
                self.assertEqual(SCHOLARSHIP_LOGOS[type_], expected)

    def test_no_catalogue_programme_falls_back_to_the_bipsu_seal_by_accident(self):
        unmapped = sorted(t for t in BY_TYPE if t not in SCHOLARSHIP_LOGOS)
        self.assertEqual(unmapped, ['GSIS'])

    def test_fhe_is_not_something_a_student_declares(self):
        self.assertNotIn('FHE', DECLARABLE)

    def test_holding_fhe_could_not_block_a_tes_application(self):
        self.assertTrue(can_hold_alongside(held=set(), wanted='TES'))
        self.assertFalse(can_hold_alongside(held={'DOST'}, wanted='TES'))

    def test_the_awards_a_student_can_declare_gained_the_verifiable_two(self):
        self.assertIn('SUC-TDP', DECLARABLE)
        self.assertIn('JLSS', DECLARABLE)

    def test_seeding_creates_them_and_is_idempotent(self):
        added, _ = catalogue.ensure_scholarships()
        for name in ('Free Higher Education (FHE)',
                     'SUC-TDP (Tulong Dunong for SUCs)',
                     'Junior Level Science Scholarship (JLSS)'):
            self.assertIn(name, added)

        added_again, updated_again = catalogue.ensure_scholarships()
        self.assertEqual((added_again, updated_again), ([], []),
                         'a second run must change nothing')

    def test_the_landing_page_lists_them_under_their_own_seals(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        catalogue.ensure_scholarships()

        html = Client().get('/').content.decode()
        self.assertIn('Free Higher Education', html)
        self.assertIn('Junior Level Science Scholarship', html)
        self.assertIn('/media/logos/DOST.png', html)
        self.assertIn('/media/logos/UniFAST.png', html)

    def test_an_unconfigured_new_programme_still_gets_a_table(self):
        from api import scholar_columns

        for type_ in ('FHE', 'SUC-TDP', 'JLSS'):
            with self.subTest(type=type_):
                self.assertTrue(scholar_columns.default_for(type_))

    def test_every_catalogue_row_has_what_the_model_requires(self):
        required = {'name', 'type', 'category', 'group', 'description',
                    'eligibility', 'requirements', 'is_active'}
        for row in catalogue.SCHOLARSHIPS:
            with self.subTest(type=row['type']):
                self.assertEqual(required - set(row), set())

    def test_no_two_programmes_share_a_type(self):
        types = [row['type'] for row in catalogue.SCHOLARSHIPS]
        self.assertEqual(len(types), len(set(types)))

    def test_the_catalogue_and_the_database_agree_after_seeding(self):
        catalogue.ensure_scholarships()
        self.assertEqual(Scholarship.objects.count(), len(catalogue.SCHOLARSHIPS))


class GuidelineBenefitsTest(TestCase):
    def benefits(self, type_):
        return ' '.join(BY_TYPE[type_]['benefits'])

    def test_tes_quotes_the_suc_rate(self):
        text = self.benefits('TES')
        self.assertIn('10,000 per semester', text)
        self.assertIn('20,000', text)

    def test_tes_does_not_quote_the_private_hei_rate(self):
        self.assertNotIn('13,500', self.benefits('TES'))
        self.assertNotIn('27,000', self.benefits('TES'))

    def test_tes_names_its_three_additional_grants(self):
        text = self.benefits('TES')
        self.assertIn('TES-3A', text)
        self.assertIn('TES-3B', text)
        self.assertIn('SARDO', text)

    def test_tdp_is_a_flat_grant_not_a_stipend_package(self):
        text = self.benefits('TDP')
        self.assertIn('7,500 per semester', text)
        self.assertIn('15,000', text)
        self.assertNotIn('Monthly stipend', text)
        self.assertNotIn('Book and supplies', text)

    def test_the_suc_tulong_dunong_line_is_paid_at_the_same_rate(self):
        self.assertIn('7,500 per semester', self.benefits('SUC-TDP'))

    def test_fhe_qualifies_what_free_covers(self):
        self.assertIn('First copy', self.benefits('FHE'))

    def test_the_grants_that_stack_with_fhe_say_so(self):
        for type_ in ('TDP', 'SUC-TDP', 'FHE'):
            with self.subTest(type=type_):
                self.assertIn('Free Higher Education', self.benefits(type_))

    def test_no_benefit_figures_were_invented_for_the_other_programmes(self):
        for type_ in ('DOST', 'JLSS', 'CHED', 'CoScho', 'GSIS'):
            with self.subTest(type=type_):
                self.assertNotIn('7,500 per semester', self.benefits(type_))
                self.assertNotIn('10,000 per semester', self.benefits(type_))

    def test_the_leak_check_reads_rates_not_loose_digits(self):
        self.assertIn('17,500', self.benefits('CHED'))
        self.assertIn('7,500 per semester', self.benefits('TDP'))


class CoSchoGuidelinesTest(TestCase):
    def setUp(self):
        self.entry = BY_TYPE['CoScho']
        self.benefits = ' '.join(self.entry['benefits'])
        self.eligibility = ' '.join(self.entry['eligibility_list'])

    def test_the_total_and_both_halves_of_it_are_quoted(self):
        self.assertIn('195,000', self.benefits)
        self.assertIn('80,000', self.benefits)
        self.assertIn('115,000', self.benefits)

    def test_the_regular_allowances_are_per_semester(self):
        self.assertIn('35,000 per semester', self.benefits)
        self.assertIn('70,000', self.benefits)
        self.assertIn('5,000 per semester', self.benefits)

    def test_the_one_off_allowances_are_all_three_named(self):
        for amount in ('75,000', '10,000', '30,000'):
            with self.subTest(amount=amount):
                self.assertIn(amount, self.benefits)

    def test_the_laptop_and_conference_grants_say_they_are_once_only(self):
        self.assertIn('once', self.benefits)

    def test_it_does_not_promise_tuition_or_a_clothing_allowance(self):
        lowered = self.benefits.lower()
        self.assertNotIn('tuition', lowered)
        self.assertNotIn('clothing', lowered)

    def test_the_farmer_themself_qualifies_not_only_a_dependent(self):
        self.assertIn('or', self.eligibility.lower())
        self.assertIn('dependent', self.eligibility)
        self.assertNotIn('Child or legal dependent', self.eligibility)

    def test_the_registry_is_the_ncfrs(self):
        self.assertIn('NCFRS', self.eligibility)
        self.assertNotIn('PCIC', self.eligibility)

    def test_the_grade_and_income_gates_are_stated(self):
        self.assertIn('80%', self.eligibility)
        self.assertIn('300,000', self.eligibility)

    def test_both_entry_points_into_the_programme_are_described(self):
        self.assertIn('high school', self.eligibility)
        self.assertIn('college student', self.eligibility)
        self.assertIn('PCA', self.eligibility)

    def test_the_bar_on_other_government_aid_is_stated(self):
        self.assertIn('government-funded', self.eligibility)

    def test_the_checklist_covers_all_three_kinds_of_applicant(self):
        papers = ' '.join(self.entry['requirements'])
        self.assertIn('Grade 11', papers)
        self.assertIn('Form 138', papers)
        self.assertIn('latest semester or term', papers)

    def test_only_one_family_member_may_apply(self):
        papers = ' '.join(self.entry['requirements'])
        self.assertIn('PCA Certification', papers)
        self.assertIn('only one member of a family', papers)

    def test_proof_of_income_lists_every_accepted_alternative(self):
        papers = ' '.join(self.entry['requirements'])
        for proof in ('ITR', 'Tax Exemption', 'No Income', 'Indigency', 'DSWD'):
            with self.subTest(proof=proof):
                self.assertIn(proof, papers)

    def test_the_conditional_papers_are_marked_conditional(self):
        conditional = [r for r in self.entry['requirements']
                       if 'if applicable' in r]
        self.assertEqual(len(conditional), 2)


class CharterProgrammesTest(TestCase):
    def field(self, type_, key):
        return ' '.join(BY_TYPE[type_][key])

    def test_ched_quotes_both_tiers_with_their_totals(self):
        text = self.field('CHED', 'benefits')
        self.assertIn('80,000', text)
        self.assertIn('40,000', text)
        self.assertIn('Full Merit', text)
        self.assertIn('Half Merit', text)

    def test_both_ched_tiers_are_broken_into_their_three_parts(self):
        text = self.field('CHED', 'benefits')
        for amount in ('35,000', '5,000', '17,500', '2,500'):
            with self.subTest(amount=amount):
                self.assertIn(amount, text)

    def test_the_ched_tiers_match_the_stored_tier_choices(self):
        from api.constants import CHED_TIER_CHOICES

        text = self.field('CHED', 'benefits')
        for value, _ in CHED_TIER_CHOICES:
            with self.subTest(tier=value):
                self.assertIn(value, text)

    def test_the_ched_grade_gates_are_percentages_not_a_gwa_point_score(self):
        text = self.field('CHED', 'eligibility_list')
        self.assertIn('96%', text)
        self.assertIn('93%', text)
        self.assertNotIn('1.75', text)

    def test_the_ched_income_ceiling_is_four_hundred_thousand(self):
        text = self.field('CHED', 'eligibility_list')
        self.assertIn('400,000', text)
        self.assertNotIn('300,000', text)

    def test_the_ched_ceiling_records_that_it_can_be_waived(self):
        self.assertIn('slightly above', self.field('CHED', 'eligibility_list'))

    def test_sports_cites_the_board_resolution_that_sets_the_grant(self):
        for key in ('benefits', 'eligibility_list'):
            with self.subTest(key=key):
                self.assertIn('Board Resolution No. 14', self.field('Sports', key))

    def test_sports_quotes_the_range_not_an_invented_package(self):
        text = self.field('Sports', 'benefits')
        self.assertIn('5,000', text)
        self.assertIn('10,000', text)
        self.assertNotIn('tuition', text.lower())

    def test_sports_asks_for_proof_of_competition(self):
        papers = self.field('Sports', 'requirements')
        self.assertIn('Certificate of Award', papers)
        self.assertIn('Medals', papers)

    def test_the_jlss_tracks_include_ra_10612(self):
        text = self.field('JLSS', 'eligibility_list')
        for track in ('RA 10612', 'RA 7687', 'Merit'):
            with self.subTest(track=track):
                self.assertIn(track, text)

    def test_both_dost_programmes_name_bipsu_s_priority_courses(self):
        for type_ in ('DOST', 'JLSS'):
            with self.subTest(type=type_):
                text = self.field(type_, 'eligibility_list')
                for course in ('BSCE', 'BSCS', 'BSCpE', 'BSEE',
                               'BSIS', 'BSME', 'BSEd Mathematics', 'BSEd Science'):
                    self.assertIn(course, text)

    def test_the_staff_grant_covers_the_employee_as_well_as_a_dependent(self):
        entry = BY_TYPE['Staff']
        self.assertIn('permanent', entry['description'].lower())
        self.assertNotEqual(entry['eligibility'], 'Dependent of BiPSU employee')

    def test_a_graduate_dependent_is_still_disqualified(self):
        self.assertIn('baccalaureate', self.field('Staff', 'eligibility_list'))

    def test_the_charter_did_not_reopen_tes_or_tdp(self):
        text = self.field('TES', 'benefits')
        self.assertIn('10,000 per semester', text)
        self.assertNotIn('27,000', text)

    def test_the_two_gaps_the_charter_was_allowed_to_fill(self):
        papers = self.field('TES', 'requirements')
        self.assertIn('Certificate of Registration', papers)
        self.assertIn('PWD ID', papers)
        self.assertIn('400,000', self.field('TDP', 'eligibility_list'))

    def test_the_residency_paper_says_it_is_not_a_bipsu_one(self):
        residency = [r for r in BY_TYPE['TES']['requirements']
                     if 'Residency' in r]
        self.assertEqual(len(residency), 1)
        self.assertIn('never of a BiPSU grantee', residency[0])

    def test_the_charter_did_not_also_rewrite_the_tes_rates(self):
        text = self.field('TES', 'benefits')
        for grant in ('TES-3A', 'TES-3B', 'SARDO'):
            with self.subTest(grant=grant):
                self.assertIn(grant, text)

    def test_no_rebel_returnee_group_was_added(self):
        entry = BY_TYPE['Affirmative']
        prose = ' '.join(entry['eligibility_list']) + ' ' + entry['background']
        self.assertNotIn('rebel', prose.lower())
        self.assertNotIn('returnee', prose.lower())

    def test_affirmative_still_answers_to_the_pasuc_proposal(self):
        text = self.field('Affirmative', 'eligibility_list')
        for group in ('indigenous', 'disabilities', 'public schools', 'depressed'):
            with self.subTest(group=group):
                self.assertIn(group, text)


class CatalogueProseTest(TestCase):
    def strings(self):
        for row in catalogue.SCHOLARSHIPS:
            for key in ('name', 'description', 'eligibility', 'background'):
                yield row['type'], key, row[key]
            for key in ('eligibility_list', 'benefits', 'requirements'):
                for item in row.get(key) or ():
                    yield row['type'], key, item

    CAMEL_CASE_NAMES = ('DepEd',)

    def test_no_two_words_ran_together_at_a_line_wrap(self):
        import re

        def scanned(text):
            for name in self.CAMEL_CASE_NAMES:
                text = text.replace(name, '')
            return text

        faults = [f'{t}.{k}: {m.group(0)!r}'
                  for t, k, text in self.strings()
                  for m in re.finditer(r'[a-z]{2,}[A-Z][a-z]', scanned(text))]
        self.assertEqual(faults, [], 'words joined without their space: '
                                     + '; '.join(faults))

    def test_the_camel_case_exception_is_not_a_hole_in_the_check(self):
        import re

        text = 'DepEd and the noother programme'
        for name in self.CAMEL_CASE_NAMES:
            text = text.replace(name, '')
        self.assertTrue(re.search(r'[a-z]{2,}[A-Z][a-z]', 'a runTogether word'))
        self.assertIn('noother', text)

    def test_no_space_was_inserted_inside_a_hyphenated_word(self):
        import re

        faults = [f'{t}.{k}: {m.group(0)!r}'
                  for t, k, text in self.strings()
                  for m in re.finditer(r'\w- \w', text)]
        self.assertEqual(faults, [], 'hyphenated words split: ' + '; '.join(faults))

    def test_no_string_carries_doubled_or_edge_whitespace(self):
        import re

        faults = [f'{t}.{k}: {text!r}'
                  for t, k, text in self.strings()
                  if re.search(r'\s{2,}', text) or text != text.strip()]
        self.assertEqual(faults, [], 'stray whitespace: ' + '; '.join(faults))
