"""The TES rule-based recommender, now the SDSO's.

The rule these tests exist to protect: **TES is decided on complete records
only**. A student still missing an answer is screened out before any rule runs
— not ranked, not failed, not listed — so most of what follows is about the
line between a record the rules can be run against and one they cannot.

That line is the whole of how incompleteness is handled. Past the screen every
rule is a plain PASS or FAIL, and the tests below hold that: a rule that needed
a third verdict would mean the screen had let something through.

The other thing pinned here is where the facts live. Nobody applies for TES in
this system any more — UniFAST awards it, outside the portal — so every field
the rules read is on the student's own record, entered at registration and
correctable on My Profile. A rule that could only be answered by a form nobody
can fill in would keep that student off the list forever.
"""
from datetime import date

from django.test import Client, TestCase

from api import tes_ranking
from api.models import (
    Application, Scholarship, ScholarshipLinkRequest, StudentProfile, User,
)

COMPLETE = dict(
    citizenship='Filipino',
    school='School of Technologies and Computer Studies',
    course='BSCS',
    year_level=2,
    has_previous_degree=False,
    year_first_enrolled=date.today().year - 1,
    family_income=120000.0,
    household_size=5,
    is_listahanan_household=False,
    is_4ps_beneficiary=False,
    is_solo_parent_dependent=False,
    # The screen requires an answer here. 'NO' is how CHED's own Disability_List
    # declines the question, and _stated reads it as a no rather than a PWD.
    disability_type='NO',
)


def make_student(email, student_id, **overrides):
    user = User.objects.create_user(
        username=email, email=email, password='pw', role='student',
        first_name='Test', last_name=overrides.pop('last_name', 'Student'),
    )
    fields = dict(COMPLETE)
    fields.update(overrides)
    return StudentProfile.objects.create(user=user, student_id=student_id, **fields)


class CompleteDataTest(TestCase):
    """A student whose record is fully populated gets a decided answer."""

    def setUp(self):
        self.profile = make_student('ana@bipsu.edu.ph', '2022-00111')

    def test_every_rule_passes_and_the_student_is_eligible(self):
        e = tes_ranking.evaluate(self.profile)
        self.assertEqual(e.status, tes_ranking.ELIGIBLE)
        self.assertTrue(all(r.passed for r in e.rules), [r.verdict for r in e.rules])
        self.assertEqual(e.reason, '')

    def test_per_capita_income_is_income_over_household_size(self):
        e = tes_ranking.evaluate(self.profile)
        self.assertEqual(e.per_capita_income, 24000.0)

    def test_no_priority_1_group_lands_the_student_in_priority_2(self):
        e = tes_ranking.evaluate(self.profile)
        self.assertEqual(e.priority, tes_ranking.PRIORITY_2)
        self.assertEqual(e.recommendation, 'Recommended')

    def test_every_rule_names_the_field_it_read(self):
        # Auditability: an officer must be able to check the source of a verdict.
        for rule in tes_ranking.evaluate(self.profile).rules:
            self.assertTrue(rule.source, f'{rule.key} does not say where it read from')
            self.assertTrue(rule.detail, f'{rule.key} does not explain itself')

    def test_nothing_it_reads_comes_from_outside_the_student_record(self):
        """Every source is a StudentProfile field or the office's own records.

        The recommender used to read a TES application for three of its answers.
        There is no such form now, so a rule sourced anywhere else is one no
        screen can ever satisfy.
        """
        allowed = ('StudentProfile.', 'Application', 'ScholarshipLinkRequest')
        for rule in tes_ranking.evaluate(self.profile).rules:
            self.assertTrue(rule.source.startswith(allowed),
                            f'{rule.key} reads from {rule.source}')

    def test_the_same_input_always_gives_the_same_answer(self):
        first = tes_ranking.evaluate(self.profile)
        second = tes_ranking.evaluate(StudentProfile.objects.get(pk=self.profile.pk))
        self.assertEqual(
            [(r.key, r.verdict) for r in first.rules],
            [(r.key, r.verdict) for r in second.rules])
        self.assertEqual((first.status, first.priority), (second.status, second.priority))


class ScreenTest(TestCase):
    """An unanswered question keeps a student off the list entirely.

    Not failed and not flagged - absent. The office sees a count of how many
    were held back and nothing else about them, which is the trade the policy
    makes: a short list every row of which was decided on full data, against no
    way to tell from this page who is missing what.
    """

    def _screen(self, **overrides):
        StudentProfile.objects.all().delete()
        User.objects.all().delete()
        profile = make_student('x@bipsu.edu.ph', '2022-00999', **overrides)
        return profile, tes_ranking.missing_answers(profile)

    def test_a_complete_record_lacks_nothing(self):
        _, gaps = self._screen()
        self.assertEqual(gaps, ())

    def test_every_answer_a_rule_reads_is_one_the_screen_requires(self):
        """The screen and the rules must ask for the same things.

        A field a rule reads but the screen does not check is exactly how a
        record with a hole in it reaches evaluate(), where nothing is left to
        catch it.
        """
        profile, _ = self._screen()
        blank = {'citizenship': '', 'disability_type': ''}
        for attribute, label in tes_ranking.REQUIRED_ANSWERS:
            original = getattr(profile, attribute)
            setattr(profile, attribute, blank.get(attribute))
            self.assertIn(label, tes_ranking.unanswered_on_record(profile),
                          f'{attribute} blank did not hold the student back')
            setattr(profile, attribute, original)

    def test_a_blank_citizenship_holds_the_student_back_rather_than_failing(self):
        profile, gaps = self._screen(citizenship='')
        self.assertIn('Citizenship', gaps)
        self.assertEqual(tes_ranking.rank([profile]), [])

    def test_a_missing_school_holds_the_student_back(self):
        _, gaps = self._screen(school='')
        self.assertIn('School', gaps)

    def test_an_unknown_institution_is_not_assumed_ched_recognised(self):
        """Not a failure: this system cannot place the school, so it cannot say."""
        _, gaps = self._screen(school='Some Other College')
        self.assertIn('CHED recognition of "Some Other College"', gaps)

    def test_an_unchecked_listahanan_and_4ps_holds_the_student_back(self):
        _, gaps = self._screen(is_listahanan_household=None, is_4ps_beneficiary=None)
        self.assertIn('Listahanan / 4Ps listing', gaps)

    def test_either_one_of_listahanan_or_4ps_is_enough_to_decide_priority(self):
        _, gaps = self._screen(is_listahanan_household=None, is_4ps_beneficiary=False)
        self.assertNotIn('Listahanan / 4Ps listing', gaps)

    def test_screen_splits_a_cohort_into_decidable_and_not(self):
        whole = make_student('a@bipsu.edu.ph', '2022-00001', last_name='Whole')
        holed = make_student('b@bipsu.edu.ph', '2022-00002', last_name='Holed',
                             citizenship='')
        complete, incomplete = tes_ranking.screen([whole, holed])
        self.assertEqual(complete, [whole])
        self.assertEqual(incomplete, [holed])

    def test_rank_omits_the_held_back_and_numbers_the_rest_from_one(self):
        make_student('a@bipsu.edu.ph', '2022-00001', last_name='Whole')
        make_student('b@bipsu.edu.ph', '2022-00002', last_name='Holed', citizenship='')
        ranked = tes_ranking.rank(StudentProfile.objects.all())
        self.assertEqual([e.student_id for e in ranked], ['2022-00001'])
        self.assertEqual([e.rank for e in ranked], [1])

    def test_the_screen_asks_once_per_cohort_not_once_per_student(self):
        """The declaration lookup is a query; doing it per row is how it grows."""
        for n in range(6):
            make_student(f's{n}@bipsu.edu.ph', f'2022-0000{n}', last_name=f'S{n}')
        profiles = list(StudentProfile.objects.select_related(
            'user', *StudentProfile.DETAIL_RELATIONS))
        with self.assertNumQueries(1):
            tes_ranking.screen(profiles)


class ConfirmedFailuresTest(TestCase):
    """What an answered question can still fail on. These are real verdicts."""

    def _evaluate(self, **overrides):
        StudentProfile.objects.all().delete()
        User.objects.all().delete()
        return tes_ranking.evaluate(make_student('x@bipsu.edu.ph', '2022-00999', **overrides))

    def test_a_non_filipino_citizenship_does_fail(self):
        e = self._evaluate(citizenship='American')
        self.assertEqual(e.rule('citizenship').verdict, tes_ranking.FAIL)
        self.assertEqual(e.status, tes_ranking.NOT_ELIGIBLE)

    def test_a_confirmed_previous_degree_does_fail(self):
        e = self._evaluate(has_previous_degree=True)
        self.assertEqual(e.rule('first_degree').verdict, tes_ranking.FAIL)
        self.assertEqual(e.status, tes_ranking.NOT_ELIGIBLE)

    def test_exceeding_the_allowed_years_including_grace_does_fail(self):
        e = self._evaluate(year_first_enrolled=date.today().year - 9)
        self.assertEqual(e.rule('maximum_years').verdict, tes_ranking.FAIL)
        self.assertEqual(e.status, tes_ranking.NOT_ELIGIBLE)

    def test_the_grace_year_is_allowed(self):
        # Four-year programme plus one year of grace: the fifth year still passes.
        e = self._evaluate(year_first_enrolled=date.today().year - 4)
        self.assertEqual(e.rule('maximum_years').verdict, tes_ranking.PASS)

    def test_every_rule_is_pass_or_fail_and_nothing_else(self):
        """Past the screen there is no third verdict left to reach."""
        for e in (self._evaluate(), self._evaluate(citizenship='American'),
                  self._evaluate(has_previous_degree=True)):
            for rule in e.rules:
                self.assertIn(rule.verdict, (tes_ranking.PASS, tes_ranking.FAIL))

    def test_the_reason_names_the_rules_that_failed(self):
        e = self._evaluate(citizenship='American', has_previous_degree=True)
        self.assertIn('Citizenship', e.reason)
        self.assertIn('First College Degree', e.reason)

    def test_a_failure_is_not_recommended(self):
        self.assertEqual(self._evaluate(has_previous_degree=True).recommendation,
                         'Not Recommended')


class IncomeIsNeverInventedTest(TestCase):
    """family_income defaults to 0.0, which must not read as a household of P0."""

    def _screen(self, **overrides):
        StudentProfile.objects.all().delete()
        User.objects.all().delete()
        profile = make_student('x@bipsu.edu.ph', '2022-00999', **overrides)
        return profile, tes_ranking.missing_answers(profile)

    def test_the_zero_default_is_read_as_missing_not_as_destitution(self):
        profile, gaps = self._screen(family_income=0.0)
        self.assertIn('Household income', gaps)
        self.assertEqual(tes_ranking.rank([profile]), [],
                         'a student with no income on file was ranked anyway')

    def test_a_missing_household_size_holds_the_student_back(self):
        _, gaps = self._screen(household_size=None)
        self.assertIn('Household size', gaps)

    def test_a_household_of_zero_is_missing_not_a_division_by_zero(self):
        _, gaps = self._screen(household_size=0)
        self.assertIn('Household size', gaps)

    def test_no_ranked_student_is_ever_short_an_income(self):
        """The screen is what lets sort_key compare incomes without a guard."""
        make_student('a@bipsu.edu.ph', '2022-00001', last_name='Poor',
                     family_income=60000.0, household_size=6)
        make_student('b@bipsu.edu.ph', '2022-00002', last_name='Unknown',
                     family_income=0.0, household_size=None)
        ranked = tes_ranking.rank(StudentProfile.objects.all())
        self.assertEqual([e.student_id for e in ranked], ['2022-00001'])
        self.assertTrue(all(e.per_capita_income is not None for e in ranked))


class PriorityLevelTest(TestCase):
    def _evaluate(self, **overrides):
        StudentProfile.objects.all().delete()
        User.objects.all().delete()
        profile = make_student('x@bipsu.edu.ph', '2022-00999', **overrides)
        return tes_ranking.evaluate(StudentProfile.objects.get(pk=profile.pk))

    def test_a_listahanan_household_is_priority_1(self):
        e = self._evaluate(is_listahanan_household=True)
        self.assertEqual(e.priority, tes_ranking.PRIORITY_1)
        self.assertIn('Listahanan household', e.priority_markers)
        self.assertEqual(e.recommendation, 'High Priority')

    def test_4ps_stands_in_when_listahanan_was_never_checked(self):
        e = self._evaluate(is_listahanan_household=None, is_4ps_beneficiary=True)
        self.assertEqual(e.priority, tes_ranking.PRIORITY_1)
        self.assertIn('4Ps beneficiary', e.priority_markers)

    def test_pwd_ip_and_solo_parent_each_reach_priority_1(self):
        # Naming a disability is the PWD declaration — there is no separate
        # is_pwd column to set. StudentProfile.is_pwd derives from this.
        self.assertEqual(
            self._evaluate(disability_type='Visual Disability').priority,
            tes_ranking.PRIORITY_1)
        self.assertEqual(self._evaluate(indigenous_group='Aeta').priority,
                         tes_ranking.PRIORITY_1)
        self.assertEqual(self._evaluate(is_solo_parent_dependent=True).priority,
                         tes_ranking.PRIORITY_1)

    def test_na_in_a_free_text_field_is_an_answer_of_no_not_a_disability(self):
        # Real records in this system hold the literal string "N/A".
        e = self._evaluate(disability_type='N/A', indigenous_group='None')
        self.assertEqual(e.priority, tes_ranking.PRIORITY_2)
        self.assertEqual(e.priority_markers, [])

    def test_no_priority_1_group_confirmed_means_priority_2(self):
        self.assertEqual(self._evaluate().priority, tes_ranking.PRIORITY_2)

    def test_priority_is_only_ever_one_of_the_two(self):
        """There is no third priority left: the screen settles the inputs first.

        Both questions that used to leave it unfinalised - the Listahanan / 4Ps
        listing and solo parent status - now hold the student off the list
        instead, so every ranked row has a priority that was decided, not
        defaulted.
        """
        for overrides in ({}, {'is_listahanan_household': True},
                          {'is_solo_parent_dependent': True}):
            self.assertIn(self._evaluate(**overrides).priority,
                          (tes_ranking.PRIORITY_1, tes_ranking.PRIORITY_2))

    def test_priority_1_sorts_above_priority_2_even_on_a_higher_income(self):
        rich_p1 = make_student('a@bipsu.edu.ph', '2022-00001', last_name='Ap1',
                               is_listahanan_household=True,
                               family_income=500000.0, household_size=2)
        poor_p2 = make_student('b@bipsu.edu.ph', '2022-00002', last_name='Bp2',
                               family_income=20000.0, household_size=8)
        ranked = tes_ranking.rank([poor_p2, rich_p1])
        self.assertEqual(ranked[0].profile, rich_p1)

    def test_within_a_priority_the_lowest_per_capita_income_ranks_first(self):
        poorer = make_student('a@bipsu.edu.ph', '2022-00001', last_name='Poorer',
                              is_listahanan_household=True, family_income=50000.0, household_size=10)
        richer = make_student('b@bipsu.edu.ph', '2022-00002', last_name='Richer',
                              is_listahanan_household=True, family_income=50000.0, household_size=2)
        ranked = tes_ranking.rank([richer, poorer])
        self.assertEqual(ranked[0].profile, poorer)
        self.assertLess(ranked[0].per_capita_income, ranked[1].per_capita_income)


class ConflictingAssistanceTest(TestCase):
    def setUp(self):
        self.profile = make_student('ana@bipsu.edu.ph', '2022-00111')

    def _award(self, stype):
        scholarship = Scholarship.objects.create(name=stype, type=stype, category='Needs-Based')
        Application.objects.create(student=self.profile, scholarship=scholarship,
                                   status='Approved', form_data={})

    def test_an_approved_government_award_on_file_fails_the_rule(self):
        self._award('TDP')
        e = tes_ranking.evaluate(self.profile)
        self.assertEqual(e.rule('other_assistance').verdict, tes_ranking.FAIL)
        self.assertEqual(e.status, tes_ranking.NOT_ELIGIBLE)

    def test_a_linked_government_scholarship_counts_too(self):
        ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='DOST', status='Approved',
            proof_document='x.pdf')
        self.assertEqual(
            tes_ranking.evaluate(self.profile).rule('other_assistance').verdict,
            tes_ranking.FAIL)

    def test_an_institutional_award_is_not_government_assistance(self):
        self._award('Academic')
        self.assertEqual(
            tes_ranking.evaluate(self.profile).rule('other_assistance').verdict,
            tes_ranking.PASS)

    def test_an_unverified_declaration_holds_the_student_back(self):
        """Declared at registration, not yet decided by the office.

        It may be ongoing government assistance, which disqualifies, or
        one-time emergency help, which does not. Nobody knows until the proof
        is looked at, so the student is screened out rather than guessed at -
        the conflict rule can neither pass nor fail on it.
        """
        ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='DOST', status='Pending',
            proof_document='x.pdf')
        gaps = tes_ranking.missing_answers(self.profile)
        self.assertIn('A decision on DOST', gaps)
        self.assertEqual(tes_ranking.rank([self.profile]), [])

    def test_a_pending_application_is_not_an_award(self):
        scholarship = Scholarship.objects.create(name='TDP', type='TDP', category='Needs-Based')
        Application.objects.create(student=self.profile, scholarship=scholarship,
                                   status='Pending Validation', form_data={})
        self.assertEqual(
            tes_ranking.evaluate(self.profile).rule('other_assistance').verdict,
            tes_ranking.PASS)


class RankingPageTest(TestCase):
    """The recommender is the SDSO's, on the Student Ranking page's TES tab."""

    URL = '/vpsea/ranking/?type=TES'

    def setUp(self):
        User.objects.create_user(username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
                                 password='pw', role='vpsea')
        self.eligible = make_student('a@bipsu.edu.ph', '2022-00001', last_name='Complete',
                                     is_listahanan_household=True)
        self.unknown = make_student('b@bipsu.edu.ph', '2022-00002', last_name='Unknown',
                                    citizenship='', family_income=0.0, household_size=None)
        self.c = Client()
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))

    def test_every_student_is_screened_because_nobody_applies(self):
        """There is no application to filter on, so the population is everyone."""
        r = self.c.get(self.URL)
        self.assertEqual(r.context['tes_student_total'] + r.context['tes_excluded'], 2)

    def test_only_students_with_a_complete_record_are_ranked(self):
        r = self.c.get(self.URL)
        ranked = [e.student_id for e in r.context['tes_rows']]
        self.assertEqual(ranked, ['2022-00001'])
        # Ranks are contiguous from 1, not inherited from the wider evaluation.
        self.assertEqual([e.rank for e in r.context['tes_rows']], [1])

    def test_an_incomplete_record_is_counted_and_not_otherwise_shown(self):
        """The count is the only trace the office gets - by design, and a cost.

        Nothing on the page names the held-back student or says what they lack,
        so a record with one answer missing is invisible here until somebody
        goes looking for it.
        """
        r = self.c.get(self.URL)
        self.assertEqual(r.context['tes_excluded'], 1)
        html = r.content.decode()
        self.assertNotIn('2022-00002', html)
        self.assertIn('not shown at all', html)

    def test_the_page_says_how_many_it_is_not_showing(self):
        html = self.c.get(self.URL).content.decode()
        self.assertIn('Not Shown', html)

    def test_the_page_states_what_the_order_is_based_on(self):
        html = self.c.get(self.URL).content.decode()
        self.assertIn('Priority group', html)
        self.assertIn('Household per capita income', html)
        self.assertIn('priority markers', html)
        self.assertIn('Surname', html)

    def test_the_page_says_it_recommends_rather_than_awards(self):
        """UniFAST awards TES. A page that read as an award list would be a lie."""
        html = self.c.get(self.URL).content.decode()
        self.assertIn('UniFAST awards TES', html)

    def test_the_reason_behind_a_ranking_is_available_to_the_office(self):
        html = self.c.get(self.URL).content.decode()
        self.assertIn('Why?', html)
        self.assertIn('Read from StudentProfile.citizenship', html)

    def test_the_page_shows_a_per_capita_figure_for_the_ranked_student(self):
        html = self.c.get(self.URL).content.decode()
        self.assertIn('₱', html)                # the complete student's

    def test_both_tabs_are_reachable_from_either_one(self):
        for url in ('/vpsea/ranking/', self.URL):
            html = self.c.get(url).content.decode()
            self.assertIn('href="/vpsea/ranking/?type=Affirmative"', html, url)
            self.assertIn('href="/vpsea/ranking/?type=TES"', html, url)

    def test_the_affirmative_tab_is_what_an_unknown_type_falls_back_to(self):
        html = self.c.get('/vpsea/ranking/?type=Nonsense').content.decode()
        self.assertNotIn('tesTable', html)
        self.assertIn('Fit Score', html)

    def test_a_student_cannot_reach_it(self):
        self.c.logout()
        self.assertTrue(self.c.login(email='a@bipsu.edu.ph', password='pw'))
        r = self.c.get(self.URL)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])


class ProfileFormFeedsTheRecommenderTest(TestCase):
    """The student profile page is where the TES facts are actually entered.

    Without this the recommender had six fields no form could fill, so every
    student read For Verification forever.
    """

    def setUp(self):
        self.profile = make_student(
            'ana@bipsu.edu.ph', '2022-00111',
            citizenship='', household_size=None, year_first_enrolled=None,
            is_listahanan_household=None, is_4ps_beneficiary=None,
            has_previous_degree=None, is_solo_parent_dependent=None,
            family_income=0.0)
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def _save(self, **fields):
        data = {'citizenship': '', 'household_size': '', 'year_first_enrolled': '',
                'is_listahanan_household': 'unknown', 'is_4ps_beneficiary': 'unknown',
                'has_previous_degree': 'unknown', 'is_solo_parent_dependent': 'unknown',
                'disability_type': 'NO'}
        data.update(fields)
        self.c.post('/student/profile/', data)
        self.profile.refresh_from_db()
        return self.profile

    def test_the_page_offers_every_field_the_recommender_reads(self):
        html = self.c.get('/student/profile/').content.decode()
        for name in ('citizenship', 'household_size', 'year_first_enrolled',
                     'is_listahanan_household', 'is_4ps_beneficiary',
                     'has_previous_degree', 'is_solo_parent_dependent'):
            self.assertIn(f'name="{name}"', html)

    def test_registration_asks_for_them_too(self):
        """Otherwise the office would have to chase every student individually."""
        html = Client().get('/register/').content.decode()
        for name in ('citizenship', 'household_size', 'year_first_enrolled',
                     'is_listahanan_household', 'is_4ps_beneficiary',
                     'has_previous_degree', 'is_solo_parent_dependent'):
            self.assertIn(f'name="{name}"', html)

    def test_an_untouched_form_leaves_everything_unknown(self):
        p = self._save()
        self.assertEqual(p.citizenship, '')
        self.assertIsNone(p.household_size)
        self.assertIsNone(p.is_listahanan_household)
        self.assertIsNone(p.is_4ps_beneficiary)
        self.assertIsNone(p.has_previous_degree)
        self.assertIsNone(p.is_solo_parent_dependent)

    def test_a_no_answer_is_stored_as_a_confirmed_no_not_as_unknown(self):
        p = self._save(is_listahanan_household='no', has_previous_degree='no',
                       is_solo_parent_dependent='no')
        self.assertIs(p.is_listahanan_household, False)
        self.assertIs(p.has_previous_degree, False)
        self.assertIs(p.is_solo_parent_dependent, False)

    def test_a_yes_answer_is_stored(self):
        p = self._save(is_listahanan_household='yes', is_4ps_beneficiary='yes')
        self.assertIs(p.is_listahanan_household, True)
        self.assertIs(p.is_4ps_beneficiary, True)

    def test_numbers_are_taken_and_junk_does_not_wipe_what_is_on_file(self):
        self._save(household_size='6', year_first_enrolled='2023')
        self.assertEqual(self.profile.household_size, 6)
        self.assertEqual(self.profile.year_first_enrolled, 2023)
        p = self._save(household_size='0', year_first_enrolled='abc')
        self.assertEqual(p.household_size, 6)
        self.assertEqual(p.year_first_enrolled, 2023)

    def test_filling_the_form_in_moves_a_student_onto_the_list(self):
        """The way back from invisible, and the only one the student controls."""
        self.assertEqual(tes_ranking.rank([self.profile]), [],
                         'an incomplete record was ranked before the form was filled')

        self._save(citizenship='Filipino', household_size='5',
                   year_first_enrolled=str(date.today().year - 1),
                   is_listahanan_household='yes', has_previous_degree='no',
                   is_solo_parent_dependent='no', family_income='120000')

        profile = StudentProfile.objects.get(pk=self.profile.pk)
        self.assertEqual(tes_ranking.missing_answers(profile), ())
        after = tes_ranking.evaluate(profile)
        self.assertEqual(after.status, tes_ranking.ELIGIBLE)
        self.assertEqual(after.priority, tes_ranking.PRIORITY_1)
        self.assertEqual(after.per_capita_income, 24000.0)

    def test_answering_non_filipino_is_the_one_way_to_fail_citizenship(self):
        """Failing it takes an answer. Leaving it blank keeps them off the list."""
        self._save(citizenship='Non-Filipino', household_size='5',
                   year_first_enrolled=str(date.today().year - 1),
                   is_listahanan_household='no', has_previous_degree='no',
                   is_solo_parent_dependent='no', family_income='120000')
        profile = StudentProfile.objects.get(pk=self.profile.pk)
        self.assertEqual(tes_ranking.missing_answers(profile), ())
        e = tes_ranking.evaluate(profile)
        self.assertEqual(e.rule('citizenship').verdict, tes_ranking.FAIL)
        self.assertEqual(e.status, tes_ranking.NOT_ELIGIBLE)

    def test_evaluate_refuses_a_record_that_has_not_been_screened(self):
        """The contract, enforced: no rule gets to run on a hole in the record."""
        with self.assertRaises(ValueError) as caught:
            tes_ranking.evaluate(self.profile)
        self.assertIn('has not been screened', str(caught.exception))
