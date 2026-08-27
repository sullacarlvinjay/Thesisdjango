"""The TES rule-based recommender.

The rule these tests exist to protect: missing data means NEEDS VERIFICATION,
never FAIL. Most of what follows is about what the recommender declines to
conclude when the office has not collected something yet.
"""
from datetime import date

from django.test import Client, TestCase

from api import tes_ranking
from api.models import (
    Application, Scholarship, ScholarshipLinkRequest, StudentProfile,
    TESApplication, User,
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
    """A student whose record is fully populated gets a decided answer.

    'Complete' has to include the TES application: solo-parent status lives
    there, and while it is unknown the student could still turn out to be
    Priority 1, so the recommender rightly refuses to settle their priority.
    """

    def setUp(self):
        self.profile = make_student('ana@bipsu.edu.ph', '2022-00111')
        TESApplication.objects.create(student=self.profile,
                                      is_solo_parent_dependent=False)

    def test_every_rule_passes_and_the_student_is_eligible(self):
        e = tes_ranking.evaluate(self.profile)
        self.assertEqual(e.status, tes_ranking.ELIGIBLE)
        self.assertTrue(all(r.passed for r in e.rules), [r.verdict for r in e.rules])
        self.assertEqual(e.missing, [])

    def test_per_capita_income_is_income_over_household_size(self):
        e = tes_ranking.evaluate(self.profile)
        self.assertEqual(e.per_capita_income, 24000.0)
        self.assertEqual(e.income_rank_state, tes_ranking.VERIFIED)

    def test_no_priority_1_group_lands_the_student_in_priority_2(self):
        e = tes_ranking.evaluate(self.profile)
        self.assertEqual(e.priority, tes_ranking.PRIORITY_2)
        self.assertEqual(e.recommendation, 'Recommended')

    def test_every_rule_names_the_field_it_read(self):
        # Auditability: an officer must be able to check the source of a verdict.
        for rule in tes_ranking.evaluate(self.profile).rules:
            self.assertTrue(rule.source, f'{rule.key} does not say where it read from')
            self.assertTrue(rule.detail, f'{rule.key} does not explain itself')

    def test_the_same_input_always_gives_the_same_answer(self):
        first = tes_ranking.evaluate(self.profile)
        second = tes_ranking.evaluate(StudentProfile.objects.get(pk=self.profile.pk))
        self.assertEqual(
            [(r.key, r.verdict) for r in first.rules],
            [(r.key, r.verdict) for r in second.rules])
        self.assertEqual((first.status, first.priority), (second.status, second.priority))


class MissingDataIsNotFailureTest(TestCase):
    """The heart of it: absent information must never read as a failed rule."""

    def _evaluate(self, **overrides):
        StudentProfile.objects.all().delete()
        User.objects.all().delete()
        return tes_ranking.evaluate(make_student('x@bipsu.edu.ph', '2022-00999', **overrides))

    def test_missing_citizenship_needs_verification_rather_than_failing(self):
        e = self._evaluate(citizenship='')
        self.assertEqual(e.rule('citizenship').verdict, tes_ranking.NEEDS_VERIFICATION)
        self.assertEqual(e.status, tes_ranking.FOR_VERIFICATION)
        self.assertIn('Citizenship', e.missing)

    def test_a_non_filipino_citizenship_does_fail(self):
        e = self._evaluate(citizenship='American')
        self.assertEqual(e.rule('citizenship').verdict, tes_ranking.FAIL)
        self.assertEqual(e.status, tes_ranking.NOT_ELIGIBLE)

    def test_missing_previous_degree_needs_verification(self):
        e = self._evaluate(has_previous_degree=None)
        self.assertEqual(e.rule('first_degree').verdict, tes_ranking.NEEDS_VERIFICATION)
        self.assertEqual(e.status, tes_ranking.FOR_VERIFICATION)

    def test_a_confirmed_previous_degree_does_fail(self):
        e = self._evaluate(has_previous_degree=True)
        self.assertEqual(e.rule('first_degree').verdict, tes_ranking.FAIL)
        self.assertEqual(e.status, tes_ranking.NOT_ELIGIBLE)

    def test_missing_enrolment_year_needs_verification_not_a_years_failure(self):
        e = self._evaluate(year_first_enrolled=None)
        self.assertEqual(e.rule('maximum_years').verdict, tes_ranking.NEEDS_VERIFICATION)
        self.assertIn('Year first enrolled', e.missing)

    def test_exceeding_the_allowed_years_including_grace_does_fail(self):
        e = self._evaluate(year_first_enrolled=date.today().year - 9)
        self.assertEqual(e.rule('maximum_years').verdict, tes_ranking.FAIL)
        self.assertEqual(e.status, tes_ranking.NOT_ELIGIBLE)

    def test_the_grace_year_is_allowed(self):
        # Four-year programme plus one year of grace: the fifth year still passes.
        e = self._evaluate(year_first_enrolled=date.today().year - 4)
        self.assertEqual(e.rule('maximum_years').verdict, tes_ranking.PASS)

    def test_a_missing_school_leaves_ched_recognition_unverified(self):
        e = self._evaluate(school='')
        self.assertEqual(e.rule('enrollment').verdict, tes_ranking.NEEDS_VERIFICATION)
        self.assertIn('School', e.missing)

    def test_an_unknown_institution_is_not_assumed_ched_recognised(self):
        e = self._evaluate(school='Some Other College')
        self.assertEqual(e.rule('enrollment').verdict, tes_ranking.NEEDS_VERIFICATION)
        self.assertEqual(e.status, tes_ranking.FOR_VERIFICATION)

    def test_for_verification_is_not_the_same_as_not_eligible(self):
        e = self._evaluate(citizenship='', has_previous_degree=None)
        self.assertEqual(e.status, tes_ranking.FOR_VERIFICATION)
        self.assertNotEqual(e.status, tes_ranking.NOT_ELIGIBLE)
        self.assertEqual(e.recommendation, 'For Verification')

    def test_one_confirmed_failure_outranks_any_number_of_unknowns(self):
        e = self._evaluate(citizenship='', has_previous_degree=True)
        self.assertEqual(e.status, tes_ranking.NOT_ELIGIBLE)


class IncomeIsNeverInventedTest(TestCase):
    """family_income defaults to 0.0, which must not read as a household of ₱0."""

    def _evaluate(self, **overrides):
        StudentProfile.objects.all().delete()
        User.objects.all().delete()
        return tes_ranking.evaluate(make_student('x@bipsu.edu.ph', '2022-00999', **overrides))

    def test_the_zero_default_is_read_as_missing_not_as_destitution(self):
        e = self._evaluate(family_income=0.0)
        self.assertIsNone(e.per_capita_income)
        self.assertEqual(e.income_rank_state, tes_ranking.NEEDS_VERIFICATION_LABEL)
        self.assertIn('Household income', e.missing)

    def test_a_missing_household_size_leaves_per_capita_uncomputed(self):
        e = self._evaluate(household_size=None)
        self.assertIsNone(e.per_capita_income)
        self.assertIn('Household size', e.missing)

    def test_missing_income_does_not_disqualify_anyone(self):
        e = self._evaluate(family_income=0.0, household_size=None)
        self.assertNotEqual(e.status, tes_ranking.NOT_ELIGIBLE)

    def test_a_student_with_no_income_on_file_does_not_outrank_a_poor_one(self):
        poor = make_student('poor@bipsu.edu.ph', '2022-00001',
                            last_name='Poor', family_income=60000.0, household_size=6)
        unknown = make_student('unknown@bipsu.edu.ph', '2022-00002',
                               last_name='Unknown', family_income=0.0, household_size=None)
        ranked = tes_ranking.rank([unknown, poor])
        self.assertEqual(ranked[0].profile, poor,
                         'a student with no income data was ranked as the poorest')
        self.assertEqual(ranked[1].profile, unknown)


class PriorityLevelTest(TestCase):
    def _evaluate(self, application=None, **overrides):
        StudentProfile.objects.all().delete()
        User.objects.all().delete()
        profile = make_student('x@bipsu.edu.ph', '2022-00999', **overrides)
        if application is not None:
            TESApplication.objects.create(student=profile, **application)
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
        self.assertEqual(self._evaluate(is_pwd=True).priority, tes_ranking.PRIORITY_1)
        self.assertEqual(self._evaluate(indigenous_group='Aeta').priority, tes_ranking.PRIORITY_1)
        e = self._evaluate(application={'is_solo_parent_dependent': True})
        self.assertEqual(e.priority, tes_ranking.PRIORITY_1)

    def test_na_in_a_free_text_field_is_an_answer_of_no_not_a_disability(self):
        # Real records in this system hold the literal string "N/A".
        e = self._evaluate(application={'disability_type': 'N/A',
                                        'indigenous_people_group': 'None'})
        self.assertEqual(e.priority, tes_ranking.PRIORITY_2)
        self.assertEqual(e.priority_markers, [])

    def test_no_priority_1_group_confirmed_means_priority_2(self):
        e = self._evaluate(application={'is_solo_parent_dependent': False})
        self.assertEqual(e.priority, tes_ranking.PRIORITY_2)

    def test_an_unchecked_listahanan_leaves_priority_unfinalised(self):
        e = self._evaluate(is_listahanan_household=None, is_4ps_beneficiary=None,
                           application={'is_solo_parent_dependent': False})
        self.assertEqual(e.priority, tes_ranking.PRIORITY_UNDETERMINED)
        self.assertIn('Listahanan / 4Ps listing', e.missing)

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

    def test_an_undeclared_other_scholarship_needs_verification_not_rejection(self):
        self.profile.has_other_scholarship = True
        self.profile.save()
        e = tes_ranking.evaluate(self.profile)
        self.assertEqual(e.rule('other_assistance').verdict, tes_ranking.NEEDS_VERIFICATION)
        self.assertEqual(e.status, tes_ranking.FOR_VERIFICATION)

    def test_a_pending_application_is_not_an_award(self):
        scholarship = Scholarship.objects.create(name='TDP', type='TDP', category='Needs-Based')
        Application.objects.create(student=self.profile, scholarship=scholarship,
                                   status='Pending Validation', form_data={})
        self.assertEqual(
            tes_ranking.evaluate(self.profile).rule('other_assistance').verdict,
            tes_ranking.PASS)


class RankingPageTest(TestCase):
    """The recommender belongs to UniFAST — TES is theirs to award."""

    URL = '/unifast/tes-ranking/'

    def setUp(self):
        User.objects.create_user(username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
                                 password='pw', role='unifast')
        User.objects.create_user(username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
                                 password='pw', role='vpsea')
        self.eligible = make_student('a@bipsu.edu.ph', '2022-00001', last_name='Complete',
                                     is_listahanan_household=True)
        self.unknown = make_student('b@bipsu.edu.ph', '2022-00002', last_name='Unknown',
                                    citizenship='', family_income=0.0, household_size=None)
        # Only applications still awaiting a decision are ranked.
        TESApplication.objects.create(student=self.eligible, status='Pending',
                                      is_solo_parent_dependent=False)
        TESApplication.objects.create(student=self.unknown, status='Pending',
                                      is_solo_parent_dependent=False)
        # Someone who never applied must not appear anywhere on the page.
        self.non_applicant = make_student('c@bipsu.edu.ph', '2022-00003',
                                          last_name='NeverApplied')
        self.c = Client()
        self.assertTrue(self.c.login(email='unifast@bipsu.edu.ph', password='pw'))

    def test_only_applicants_with_a_complete_record_are_ranked(self):
        r = self.c.get(self.URL)
        ranked = [e.student_id for e in r.context['tes_rows']]
        self.assertEqual(ranked, ['2022-00001'])
        # Ranks are contiguous from 1, not inherited from the wider evaluation.
        self.assertEqual([e.rank for e in r.context['tes_rows']], [1])

    def test_a_decided_application_is_no_longer_ranked(self):
        """The list exists to choose who to award. Someone already approved has
        been chosen; someone rejected has been decided against."""
        approved = make_student('d@bipsu.edu.ph', '2022-00004', last_name='Awarded',
                                is_listahanan_household=True)
        rejected = make_student('e@bipsu.edu.ph', '2022-00005', last_name='Turned',
                                is_listahanan_household=True)
        TESApplication.objects.create(student=approved, status='Approved',
                                      is_solo_parent_dependent=False)
        TESApplication.objects.create(student=rejected, status='Rejected',
                                      is_solo_parent_dependent=False)

        r = self.c.get(self.URL)
        listed = ([e.student_id for e in r.context['tes_rows']]
                  + [e.student_id for e in r.context['tes_needs_info']])
        self.assertNotIn('2022-00004', listed)
        self.assertNotIn('2022-00005', listed)
        # The one pending applicant is still there.
        self.assertIn('2022-00001', listed)

    def test_a_student_who_never_applied_is_nowhere_on_the_page(self):
        """Ranking the whole student body put non-applicants on an award list."""
        r = self.c.get(self.URL)
        listed = ([e.student_id for e in r.context['tes_rows']]
                  + [e.student_id for e in r.context['tes_needs_info']])
        self.assertNotIn('2022-00003', listed)
        self.assertNotIn('2022-00003', r.content.decode())

    def test_incomplete_applicants_are_held_back_rather_than_ranked(self):
        r = self.c.get(self.URL)
        held = [e.student_id for e in r.context['tes_needs_info']]
        self.assertEqual(held, ['2022-00002'])
        # Still visible, with what is missing named, so they can be chased.
        html = r.content.decode()
        self.assertIn('Applied, but not yet rankable', html)
        self.assertIn('2022-00002', html)
        self.assertIn('Citizenship', html)

    def test_the_page_states_what_the_order_is_based_on(self):
        html = self.c.get(self.URL).content.decode()
        self.assertIn('Priority group', html)
        self.assertIn('Household per capita income', html)
        self.assertIn('priority markers', html)
        self.assertIn('Surname', html)

    def test_the_reason_behind_a_ranking_is_available_to_the_office(self):
        html = self.c.get(self.URL).content.decode()
        self.assertIn('Why?', html)
        self.assertIn('Read from StudentProfile.citizenship', html)

    def test_the_page_shows_a_per_capita_figure_for_the_ranked_student(self):
        html = self.c.get(self.URL).content.decode()
        self.assertIn('₱', html)                # the complete student's

    def test_it_appears_in_the_unifast_sidebar(self):
        html = self.c.get(self.URL).content.decode()
        self.assertIn('href="/unifast/tes-ranking/"', html)

    def test_vpsea_cannot_reach_it(self):
        self.c.logout()
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))
        r = self.c.get(self.URL)
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('/unifast/', r['Location'])

    def test_the_vpsea_ranking_page_no_longer_offers_tes(self):
        self.c.logout()
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))
        for stype in ('Affirmative', 'Staff'):
            self.assertEqual(self.c.get(f'/vpsea/ranking/?type={stype}').status_code, 200)
        # An unknown type falls back to Affirmative rather than rendering TES.
        html = self.c.get('/vpsea/ranking/?type=TES').content.decode()
        self.assertNotIn('tesTable', html)


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
            has_previous_degree=None, family_income=0.0)
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def _save(self, **fields):
        data = {'citizenship': '', 'household_size': '', 'year_first_enrolled': '',
                'is_listahanan_household': 'unknown', 'is_4ps_beneficiary': 'unknown',
                'has_previous_degree': 'unknown'}
        data.update(fields)
        self.c.post('/student/profile/', data)
        self.profile.refresh_from_db()
        return self.profile

    def test_the_page_offers_every_field_the_recommender_reads(self):
        html = self.c.get('/student/profile/').content.decode()
        for name in ('citizenship', 'household_size', 'year_first_enrolled',
                     'is_listahanan_household', 'is_4ps_beneficiary', 'has_previous_degree'):
            self.assertIn(f'name="{name}"', html)

    def test_an_untouched_form_leaves_everything_unknown(self):
        p = self._save()
        self.assertEqual(p.citizenship, '')
        self.assertIsNone(p.household_size)
        self.assertIsNone(p.is_listahanan_household)
        self.assertIsNone(p.is_4ps_beneficiary)
        self.assertIsNone(p.has_previous_degree)

    def test_a_no_answer_is_stored_as_a_confirmed_no_not_as_unknown(self):
        p = self._save(is_listahanan_household='no', has_previous_degree='no')
        self.assertIs(p.is_listahanan_household, False)
        self.assertIs(p.has_previous_degree, False)

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

    def test_filling_the_form_in_moves_a_student_from_verification_to_eligible(self):
        before = tes_ranking.evaluate(self.profile)
        self.assertEqual(before.status, tes_ranking.FOR_VERIFICATION)

        self._save(citizenship='Filipino', household_size='5',
                   year_first_enrolled=str(date.today().year - 1),
                   is_listahanan_household='yes', has_previous_degree='no',
                   family_income='120000')
        TESApplication.objects.create(student=self.profile, is_solo_parent_dependent=False)

        after = tes_ranking.evaluate(StudentProfile.objects.get(pk=self.profile.pk))
        self.assertEqual(after.status, tes_ranking.ELIGIBLE)
        self.assertEqual(after.priority, tes_ranking.PRIORITY_1)
        self.assertEqual(after.per_capita_income, 24000.0)
        self.assertEqual(after.missing, [])

    def test_answering_non_filipino_is_the_one_way_to_fail_citizenship(self):
        self._save(citizenship='Non-Filipino')
        e = tes_ranking.evaluate(StudentProfile.objects.get(pk=self.profile.pk))
        self.assertEqual(e.rule('citizenship').verdict, tes_ranking.FAIL)
