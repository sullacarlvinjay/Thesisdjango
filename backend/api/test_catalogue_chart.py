"""The catalogue lists what the university's own programme chart says it offers.

Four programmes on BiPSU's chart had no entry at all — FHE, SUC-TDP, JLSS, and
the RA 7687 track of the DOST S&T undergraduate scholarship — so the landing
page advertised a shorter list than the university actually runs.

Two decisions are recorded here because they are the ones a later reader would
otherwise undo:

* **RA 7687 and Merit are tracks of one programme, not two programmes and not a
  stored tier.** CHED carries ``award_tier`` because every masterlist prints
  CHED in two separate blocks; nothing reports DOST that way, so a tier column
  would be a field nothing reads. The entry names both tracks instead, and
  ``type='DOST'`` is untouched — it is the key the approval routes, the archive
  tabs and ``DEFAULT_COLUMNS_BY_TYPE`` all look the programme up by.
* **FHE is not declarable.** ``SCHOLARSHIP_TYPE_CHOICES`` is the list of awards a
  student can say they already hold, and it feeds ``held_scholarship_types``.
  Free Higher Education under RA 10931 is what every qualified SUC student
  already has, so putting it there would make ``can_hold_alongside`` refuse a
  TES or DOST application from a student for holding what all of them hold.
"""
from django.test import Client, TestCase

from api import catalogue
from api.constants import SCHOLARSHIP_LOGOS, SCHOLARSHIP_TYPE_CHOICES
from api.models import Scholarship, SystemSettings
from api.student_views import can_hold_alongside

BY_TYPE = {row['type']: row for row in catalogue.SCHOLARSHIPS}
DECLARABLE = {value for value, _ in SCHOLARSHIP_TYPE_CHOICES}


class ChartProgrammesTest(TestCase):

    # ── The four that were missing ──────────────────────────────────────────

    def test_the_chart_programmes_are_all_in_the_catalogue(self):
        for type_ in ('FHE', 'SUC-TDP', 'JLSS'):
            with self.subTest(type=type_):
                self.assertIn(type_, BY_TYPE)

    def test_the_dost_entry_covers_both_of_its_tracks(self):
        """RA 7687 was represented nowhere: the entry was named for Merit alone."""
        entry = BY_TYPE['DOST']
        listed = ' '.join(entry['eligibility_list'])
        self.assertIn('RA 7687', listed)
        self.assertIn('Merit', listed)

    def test_the_dost_lookup_key_is_unchanged(self):
        """Renaming the programme is safe; renaming the key is not — archives,
        approvals and the column defaults all match on it."""
        self.assertEqual(BY_TYPE['DOST']['type'], 'DOST')

    def test_no_tier_column_was_invented_for_dost(self):
        """CHED's award_tier exists because the masterlists print two blocks.
        Nothing reports DOST that way."""
        from api.models import ScholarshipLinkRequest

        tiers = dict(ScholarshipLinkRequest._meta.get_field('award_tier').choices or [])
        self.assertNotIn('RA 7687', tiers)
        self.assertNotIn('Merit', tiers)

    # ── Who funds them ──────────────────────────────────────────────────────

    def test_each_new_programme_is_filed_under_its_funder(self):
        """The chart puts all three under an outside agency, not under BiPSU."""
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
        """GSIS is the one deliberate fallback — there is no GSIS logo on file.
        A new programme missing from the map would silently join it."""
        unmapped = sorted(t for t in BY_TYPE if t not in SCHOLARSHIP_LOGOS)
        self.assertEqual(unmapped, ['GSIS'])

    # ── FHE is listed, but not declarable ───────────────────────────────────

    def test_fhe_is_not_something_a_student_declares(self):
        """Listing it would make it exclusive — see this module's docstring."""
        self.assertNotIn('FHE', DECLARABLE)

    def test_holding_fhe_could_not_block_a_tes_application(self):
        """The failure that would follow if FHE ever became declarable, pinned
        to the rule rather than to the list."""
        self.assertTrue(can_hold_alongside(held=set(), wanted='TES'))
        # And the exclusivity rule itself is unchanged for a real award.
        self.assertFalse(can_hold_alongside(held={'DOST'}, wanted='TES'))

    def test_the_awards_a_student_can_declare_gained_the_verifiable_two(self):
        """SUC-TDP and JLSS are awarded by an agency and verifiable against the
        office's records, which is what that list is for."""
        self.assertIn('SUC-TDP', DECLARABLE)
        self.assertIn('JLSS', DECLARABLE)

    # ── What the office and the applicant actually see ──────────────────────

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
        """New types have no DEFAULT_COLUMNS_BY_TYPE entry; the archive falls
        back rather than rendering a table with no columns."""
        from api import scholar_columns

        for type_ in ('FHE', 'SUC-TDP', 'JLSS'):
            with self.subTest(type=type_):
                self.assertTrue(scholar_columns.default_for(type_))

    def test_every_catalogue_row_has_what_the_model_requires(self):
        """A row missing a key fails at seed time on a real deployment, which is
        the worst place to find out."""
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
    """The benefit figures are the ones in the UniFAST 2026 guidelines.

    Board Resolution No. 2026-012, effective 1st Semester AY 2026-2027. These
    are what a student reads on the landing page before deciding whether to
    apply, so a stale figure is a promise the office cannot keep. Pinned here so
    that when the Board revises a rate, the test says which programmes have to
    be revisited rather than leaving it to somebody noticing.

    BiPSU is a state university, so the SUC rate is the one quoted throughout.
    """

    def benefits(self, type_):
        return ' '.join(BY_TYPE[type_]['benefits'])

    def test_tes_quotes_the_suc_rate(self):
        text = self.benefits('TES')
        self.assertIn('10,000 per semester', text)
        self.assertIn('20,000', text)

    def test_tes_does_not_quote_the_private_hei_rate(self):
        """No BiPSU student is paid on it, and printing both invites a grantee
        to expect the larger one."""
        self.assertNotIn('13,500', self.benefits('TES'))
        self.assertNotIn('27,000', self.benefits('TES'))

    def test_tes_names_its_three_additional_grants(self):
        text = self.benefits('TES')
        self.assertIn('TES-3A', text)
        self.assertIn('TES-3B', text)
        self.assertIn('SARDO', text)

    def test_tdp_is_a_flat_grant_not_a_stipend_package(self):
        """What was here before described a monthly stipend, a tuition subsidy
        and a book allowance. The guidelines make it one amount per semester."""
        text = self.benefits('TDP')
        self.assertIn('7,500 per semester', text)
        self.assertIn('15,000', text)
        self.assertNotIn('Monthly stipend', text)
        self.assertNotIn('Book and supplies', text)

    def test_the_suc_tulong_dunong_line_is_paid_at_the_same_rate(self):
        self.assertIn('7,500 per semester', self.benefits('SUC-TDP'))

    def test_fhe_qualifies_what_free_covers(self):
        """The one place the deck qualifies 'free': repeat ID copies are paid for."""
        self.assertIn('First copy', self.benefits('FHE'))

    def test_the_grants_that_stack_with_fhe_say_so(self):
        """The exception that lets a student hold both, stated where they read it."""
        for type_ in ('TDP', 'SUC-TDP', 'FHE'):
            with self.subTest(type=type_):
                self.assertIn('Free Higher Education', self.benefits(type_))

    def test_no_benefit_figures_were_invented_for_the_other_programmes(self):
        """The decks cover TES, TDP and FHE. No other programme gained a peso
        figure from them, and a later reader should not assume otherwise.

        CoScho is checked here too even though it does carry figures: they come
        from its own guidelines, so a UniFAST rate appearing among them would
        mean one source had been copied into another.
        """
        for type_ in ('DOST', 'JLSS', 'CHED', 'CoScho', 'GSIS'):
            with self.subTest(type=type_):
                self.assertNotIn('7,500 per semester', self.benefits(type_))
                self.assertNotIn('10,000 per semester', self.benefits(type_))

    def test_the_leak_check_reads_rates_not_loose_digits(self):
        """CHED's ₱17,500 stipend contains '7,500'. Matching the bare number
        called that a leak of TDP's rate, so the check matches the phrase the
        UniFAST rates are always written in."""
        self.assertIn('17,500', self.benefits('CHED'))
        self.assertIn('7,500 per semester', self.benefits('TDP'))


class CoSchoGuidelinesTest(TestCase):
    """CoScho's entry is quoted from its own published guidelines.

    What stood here before was written from the programme's name alone: a
    tuition subsidy, a monthly allowance and an annual clothing allowance, none
    of which it pays, and a registry it does not use. The real grant is a fixed
    ₱195,000 of allowances, and tuition is not among them — a BiPSU student's
    tuition is already Free Higher Education's.
    """

    def setUp(self):
        self.entry = BY_TYPE['CoScho']
        self.benefits = ' '.join(self.entry['benefits'])
        self.eligibility = ' '.join(self.entry['eligibility_list'])

    # ── Benefits ────────────────────────────────────────────────────────────

    def test_the_total_and_both_halves_of_it_are_quoted(self):
        self.assertIn('195,000', self.benefits)
        self.assertIn('80,000', self.benefits)
        self.assertIn('115,000', self.benefits)

    def test_the_regular_allowances_are_per_semester(self):
        """Stipend and books are paid each term; the academic-year figure is
        stated beside each so neither is read as the whole grant."""
        self.assertIn('35,000 per semester', self.benefits)
        self.assertIn('70,000', self.benefits)
        self.assertIn('5,000 per semester', self.benefits)

    def test_the_one_off_allowances_are_all_three_named(self):
        for amount in ('75,000', '10,000', '30,000'):
            with self.subTest(amount=amount):
                self.assertIn(amount, self.benefits)

    def test_the_laptop_and_conference_grants_say_they_are_once_only(self):
        """Both are one-time in the guidelines. Printed without that, a
        grantee reads them as recurring."""
        self.assertIn('once', self.benefits)

    def test_it_does_not_promise_tuition_or_a_clothing_allowance(self):
        """Both were in the guessed entry. The guidelines pay neither."""
        lowered = self.benefits.lower()
        self.assertNotIn('tuition', lowered)
        self.assertNotIn('clothing', lowered)

    # ── Eligibility ─────────────────────────────────────────────────────────

    def test_the_farmer_themself_qualifies_not_only_a_dependent(self):
        """The guidelines say 'registered coconut farmer OR his/her
        dependent'. The guessed entry admitted only the dependent."""
        self.assertIn('or', self.eligibility.lower())
        self.assertIn('dependent', self.eligibility)
        self.assertNotIn('Child or legal dependent', self.eligibility)

    def test_the_registry_is_the_ncfrs(self):
        """It said PCIC before — the crop insurance corporation, which has
        nothing to do with the coconut farmers' registry."""
        self.assertIn('NCFRS', self.eligibility)
        self.assertNotIn('PCIC', self.eligibility)

    def test_the_grade_and_income_gates_are_stated(self):
        self.assertIn('80%', self.eligibility)
        self.assertIn('300,000', self.eligibility)

    def test_both_entry_points_into_the_programme_are_described(self):
        """A graduating high school student and a college student already in a
        PCA-identified degree are separate routes in the guidelines."""
        self.assertIn('high school', self.eligibility)
        self.assertIn('college student', self.eligibility)
        self.assertIn('PCA', self.eligibility)

    def test_the_bar_on_other_government_aid_is_stated(self):
        self.assertIn('government-funded', self.eligibility)

    # ── The documentary checklist ───────────────────────────────────────────

    def test_the_checklist_covers_all_three_kinds_of_applicant(self):
        """A senior high student, a senior high graduate and someone already in
        college each prove their grades with a different paper."""
        papers = ' '.join(self.entry['requirements'])
        self.assertIn('Grade 11', papers)
        self.assertIn('Form 138', papers)
        self.assertIn('latest semester or term', papers)

    def test_only_one_family_member_may_apply(self):
        """A restriction, carried on the PCA Certification line where the
        office reads it, not left to the guidelines."""
        papers = ' '.join(self.entry['requirements'])
        self.assertIn('PCA Certification', papers)
        self.assertIn('only one member of a family', papers)

    def test_proof_of_income_lists_every_accepted_alternative(self):
        """Five are accepted. Printing fewer turns an alternative into a
        requirement the applicant cannot meet."""
        papers = ' '.join(self.entry['requirements'])
        for proof in ('ITR', 'Tax Exemption', 'No Income', 'Indigency', 'DSWD'):
            with self.subTest(proof=proof):
                self.assertIn(proof, papers)

    def test_the_conditional_papers_are_marked_conditional(self):
        """The special-group proof and the barangay certification apply only to
        some applicants; unmarked, they read as required of everyone."""
        conditional = [r for r in self.entry['requirements']
                       if 'if applicable' in r]
        self.assertEqual(len(conditional), 2)


class CharterProgrammesTest(TestCase):
    """The entries BiPSU's own "Scholarship Flow" citizens charter governs.

    Most of these were written from the programme's name before the charter
    was available, and the guesses were not harmless: CHED Merit advertised a
    GWA gate of 1.75 and a ₱300,000 income ceiling, when the real gates are
    96% and ₱400,000 — a student reading the old entry would have ruled
    themself out of a scholarship they qualified for.
    """

    def field(self, type_, key):
        return ' '.join(BY_TYPE[type_][key])

    # ── CHED Merit ──────────────────────────────────────────────────────────

    def test_ched_quotes_both_tiers_with_their_totals(self):
        text = self.field('CHED', 'benefits')
        self.assertIn('80,000', text)
        self.assertIn('40,000', text)
        self.assertIn('Full Merit', text)
        self.assertIn('Half Merit', text)

    def test_both_ched_tiers_are_broken_into_their_three_parts(self):
        """Tuition, stipend and book/connectivity are separate lines in the
        charter. A lump sum hides which part a grantee has already drawn."""
        text = self.field('CHED', 'benefits')
        for amount in ('35,000', '5,000', '17,500', '2,500'):
            with self.subTest(amount=amount):
                self.assertIn(amount, text)

    def test_the_ched_tiers_match_the_stored_tier_choices(self):
        """`award_tier` is Full/Half; the benefit lines must name the same two
        so a masterlist block and the landing page agree."""
        from api.constants import CHED_TIER_CHOICES

        text = self.field('CHED', 'benefits')
        for value, _ in CHED_TIER_CHOICES:
            with self.subTest(tier=value):
                self.assertIn(value, text)

    def test_the_ched_grade_gates_are_percentages_not_a_gwa_point_score(self):
        """It said 'GWA ≥ 1.75' — a 5-point scale the charter never uses."""
        text = self.field('CHED', 'eligibility_list')
        self.assertIn('96%', text)
        self.assertIn('93%', text)
        self.assertNotIn('1.75', text)

    def test_the_ched_income_ceiling_is_four_hundred_thousand(self):
        """₱300,000 is CoScho's ceiling. Carrying it here turned away
        households the CMSP accepts."""
        text = self.field('CHED', 'eligibility_list')
        self.assertIn('400,000', text)
        self.assertNotIn('300,000', text)

    def test_the_ched_ceiling_records_that_it_can_be_waived(self):
        """'Special consideration may be given for those slightly above the
        limit with valid justifications' — a student just over it should not
        read the entry as a closed door."""
        self.assertIn('slightly above', self.field('CHED', 'eligibility_list'))

    # ── Sports ──────────────────────────────────────────────────────────────

    def test_sports_cites_the_board_resolution_that_sets_the_grant(self):
        for key in ('benefits', 'eligibility_list'):
            with self.subTest(key=key):
                self.assertIn('Board Resolution No. 14', self.field('Sports', key))

    def test_sports_quotes_the_range_not_an_invented_package(self):
        """Full tuition, equipment and travel allowances were all invented; the
        resolution sets a cash range per semester and nothing else."""
        text = self.field('Sports', 'benefits')
        self.assertIn('5,000', text)
        self.assertIn('10,000', text)
        self.assertNotIn('tuition', text.lower())

    def test_sports_asks_for_proof_of_competition(self):
        papers = self.field('Sports', 'requirements')
        self.assertIn('Certificate of Award', papers)
        self.assertIn('Medals', papers)

    # ── DOST and JLSS ───────────────────────────────────────────────────────

    def test_the_jlss_tracks_include_ra_10612(self):
        """JLSS runs under three tracks. RA 10612 — the one that fast-tracks
        science and mathematics teachers — was in neither the entry nor the
        eligibility list."""
        text = self.field('JLSS', 'eligibility_list')
        for track in ('RA 10612', 'RA 7687', 'Merit'):
            with self.subTest(track=track):
                self.assertIn(track, text)

    def test_both_dost_programmes_name_bipsu_s_priority_courses(self):
        """The charter lists eight. Which course a student is in decides
        eligibility, so the list belongs where they read it."""
        for type_ in ('DOST', 'JLSS'):
            with self.subTest(type=type_):
                text = self.field(type_, 'eligibility_list')
                for course in ('BSCE', 'BSCS', 'BSCpE', 'BSEE',
                               'BSIS', 'BSME', 'BSEd Mathematics', 'BSEd Science'):
                    self.assertIn(course, text)

    # ── Staff ───────────────────────────────────────────────────────────────

    def test_the_staff_grant_covers_the_employee_as_well_as_a_dependent(self):
        """It was described as 'tuition support for dependents'. The charter
        gives the privilege to the faculty and staff themselves too."""
        entry = BY_TYPE['Staff']
        self.assertIn('permanent', entry['description'].lower())
        self.assertNotEqual(entry['eligibility'], 'Dependent of BiPSU employee')

    def test_a_graduate_dependent_is_still_disqualified(self):
        self.assertIn('baccalaureate', self.field('Staff', 'eligibility_list'))

    # ── What the charter must NOT have been allowed to overwrite ────────────

    def test_the_charter_did_not_reopen_tes_or_tdp(self):
        """The charter predates the 2026 UniFAST guidelines and quotes the
        older rates — the per-academic-year TES figure and a PHEI rate. The
        deck wins, so neither may appear in the TES entry."""
        text = self.field('TES', 'benefits')
        self.assertIn('10,000 per semester', text)
        self.assertNotIn('27,000', text)

    def test_the_two_gaps_the_charter_was_allowed_to_fill(self):
        """TES had no checklist at all — a blank card on the landing page — and
        TDP carried no income ceiling. Neither contradicts a figure the 2026
        decks stated, which is the only reason the charter reaches them."""
        papers = self.field('TES', 'requirements')
        self.assertIn('Certificate of Registration', papers)
        self.assertIn('PWD ID', papers)
        self.assertIn('400,000', self.field('TDP', 'eligibility_list'))

    def test_the_residency_paper_says_it_is_not_a_bipsu_one(self):
        """It belongs to the private-HEI category in an area with no SUC or
        LUC. Listed flat, a BiPSU grantee reads it as a paper they must chase."""
        residency = [r for r in BY_TYPE['TES']['requirements']
                     if 'Residency' in r]
        self.assertEqual(len(residency), 1)
        self.assertIn('never of a BiPSU grantee', residency[0])

    def test_the_charter_did_not_also_rewrite_the_tes_rates(self):
        """Filling `requirements` is the whole of the licence the charter got
        on this entry. The deck's additional grants must survive it."""
        text = self.field('TES', 'benefits')
        for grant in ('TES-3A', 'TES-3B', 'SARDO'):
            with self.subTest(grant=grant):
                self.assertIn(grant, text)

    def test_no_rebel_returnee_group_was_added(self):
        """The charter names one; Juniel's decision on 2026-09-12 was to keep it
        out of both the entry and the ranking. Pinned because the charter is
        the obvious place a later reader would reach for to 'complete' this."""
        entry = BY_TYPE['Affirmative']
        prose = ' '.join(entry['eligibility_list']) + ' ' + entry['background']
        self.assertNotIn('rebel', prose.lower())
        self.assertNotIn('returnee', prose.lower())

    def test_affirmative_still_answers_to_the_pasuc_proposal(self):
        """The charter describes BiPSU's own framing, which adds children of
        rebel returnees to the mandate. `affirmative_ranking` orders the
        shortlist by the PASUC-8 groups, so the entry is not edited from the
        charter without that ordering being revisited."""
        text = self.field('Affirmative', 'eligibility_list')
        for group in ('indigenous', 'disabilities', 'public schools', 'depressed'):
            with self.subTest(group=group):
                self.assertIn(group, text)


class CatalogueProseTest(TestCase):
    """Every catalogue string reads as prose.

    The entries are written as adjacent string literals wrapped across source
    lines, and Python concatenates those with nothing in between. Drop the space
    the wrap consumed and 'no other' compiles to 'noother' — invisible in the
    source, plainly wrong on the landing page. It happened twice while these
    entries were being written, once on a space and once inside a hyphenated
    word, so it is checked rather than trusted to review.
    """

    def strings(self):
        for row in catalogue.SCHOLARSHIPS:
            for key in ('name', 'description', 'eligibility', 'background'):
                yield row['type'], key, row[key]
            for key in ('eligibility_list', 'benefits', 'requirements'):
                for item in row.get(key) or ():
                    yield row['type'], key, item

    # Names that really are spelled with a capital in the middle. The pattern
    # below cannot tell 'DepEd' from 'noother', so these are taken out before
    # the scan rather than the scan being loosened to let both through.
    # 'BiPSU' needs no entry: the capital after it is another capital, which
    # the pattern already does not match.
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
        """Removing 'DepEd' must not also excuse a real fault beside it."""
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
