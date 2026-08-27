"""Rule-based TES recommender: eligibility, priority and ranking, explained.

The whole point of this module is the distinction between *failing* a rule and
*not knowing* whether it was met. A student whose citizenship was never recorded
has not failed the citizenship test — nobody has run it. Every rule therefore
returns one of three verdicts, and the overall status has a matching third
state:

    PASS / FAIL / NEEDS VERIFICATION   ->   Eligible / Not Eligible / For Verification

Nothing here writes to the database and nothing here guesses. Each rule names
the field it read and, when it could not decide, names what is missing so the
office knows what to go and collect.

Two defaults in the existing schema are traps this module works around:

  * ``StudentProfile.family_income`` defaults to 0.0, so a household that never
    entered anything looks identical to one earning nothing. Ranking that
    student as the poorest applicant is exactly the error the TES rules warn
    about, so 0.0 is read as missing.
  * ``StudentProfile.is_pwd`` and ``has_other_scholarship`` are two-state
    booleans. False is treated as an answer only where the system has positive
    evidence behind it — see the individual rules.

Field mapping (requirement -> the field actually used):

    Citizenship             StudentProfile.citizenship
    Enrolled / CHED-recog.  StudentProfile.year_level, .school
    First degree            StudentProfile.has_previous_degree
    Maximum years           StudentProfile.year_first_enrolled + PROGRAM_YEARS
    Other gov. assistance   Application / ScholarshipLinkRequest rows,
                            StudentProfile.has_other_scholarship
    Listahanan              StudentProfile.is_listahanan_household
    4Ps (fallback)          StudentProfile.is_4ps_beneficiary
    Solo parent dependent   TESApplication.is_solo_parent_dependent
    ICC / IP                StudentProfile.indigenous_group,
                            TESApplication.indigenous_people_group
    PWD                     StudentProfile.is_pwd, TESApplication.disability_type
    Household income        StudentProfile.family_income
    Household size          StudentProfile.household_size
"""
from dataclasses import dataclass, field
from datetime import date

PASS = 'PASS'
FAIL = 'FAIL'
NEEDS_VERIFICATION = 'NEEDS VERIFICATION'

ELIGIBLE = 'Eligible'
NOT_ELIGIBLE = 'Not Eligible'
FOR_VERIFICATION = 'For Verification'

PRIORITY_1 = 'Priority 1'
PRIORITY_2 = 'Priority 2'
PRIORITY_UNDETERMINED = 'Cannot be finalized'

VERIFIED = 'Verified'
NEEDS_VERIFICATION_LABEL = 'Needs Verification'

# Institutional reference data, not an assumption about any student: every BiPSU
# undergraduate programme in api/constants.BIPSU_COURSES runs four years, and the
# TES rules allow a one-year grace period on top. Programmes that run longer
# belong in PROGRAM_YEARS so the rule stays correct without touching the logic.
STANDARD_PROGRAM_YEARS = 4
GRACE_YEARS = 1
PROGRAM_YEARS = {}

# Ongoing government assistance that TES cannot be held alongside. One-time
# emergency help (DSWD AICS, CHED SMART) is deliberately absent — the rules say
# it must not disqualify anyone.
CONFLICTING_GOVERNMENT_PROGRAMS = ('TDP', 'DOST', 'CHED')


@dataclass(frozen=True)
class RuleResult:
    """One eligibility rule, its verdict, and why."""
    key: str
    label: str
    verdict: str
    detail: str
    source: str = ''
    missing: tuple = ()

    @property
    def passed(self):
        return self.verdict == PASS

    @property
    def failed(self):
        return self.verdict == FAIL

    @property
    def unverified(self):
        return self.verdict == NEEDS_VERIFICATION


@dataclass
class Evaluation:
    """Everything the office needs to see, and to defend, for one student."""
    profile: object
    application: object
    rules: list
    status: str
    priority: str
    priority_markers: list
    per_capita_income: float = None
    income_rank_state: str = NEEDS_VERIFICATION_LABEL
    missing: list = field(default_factory=list)
    rank: int = None

    @property
    def student_name(self):
        return self.profile.full_name or self.profile.user.get_full_name()

    @property
    def student_id(self):
        return self.profile.student_id

    @property
    def eligible(self):
        return self.status == ELIGIBLE

    @property
    def needs_verification(self):
        return self.status == FOR_VERIFICATION

    @property
    def recommendation(self):
        """The one-line verdict shown in the Recommendation column."""
        if self.status == NOT_ELIGIBLE:
            return 'Not Recommended'
        if self.status == FOR_VERIFICATION:
            return 'For Verification'
        return 'High Priority' if self.priority == PRIORITY_1 else 'Recommended'

    def rule(self, key):
        for r in self.rules:
            if r.key == key:
                return r
        return None

    @property
    def sort_key(self):
        """Eligibility, then priority, then per-capita income, then markers.

        A student whose per-capita income is unknown sorts after everyone whose
        income is known rather than to the top or the bottom of the list: not
        knowing is not evidence of being poor, nor of being well off.
        """
        status_rank = {ELIGIBLE: 0, FOR_VERIFICATION: 1, NOT_ELIGIBLE: 2}[self.status]
        priority_rank = {PRIORITY_1: 0, PRIORITY_2: 1, PRIORITY_UNDETERMINED: 2}[self.priority]
        income_known = 0 if self.per_capita_income is not None else 1
        income = self.per_capita_income if self.per_capita_income is not None else 0.0
        return (
            status_rank,
            priority_rank,
            income_known,
            income,
            -len(self.priority_markers),
            (self.profile.user.last_name or '').lower(),
        )


# ── individual rules ────────────────────────────────────────────────────────

def _citizenship_rule(profile):
    recorded = _stated(profile.citizenship)
    if not recorded:
        return RuleResult(
            'citizenship', 'Citizenship', NEEDS_VERIFICATION,
            'Citizenship has not been recorded. It is neither assumed Filipino nor assumed otherwise.',
            source='StudentProfile.citizenship', missing=('Citizenship',))
    if recorded.casefold() in ('filipino', 'filipino citizen', 'philippine', 'pilipino'):
        return RuleResult('citizenship', 'Citizenship', PASS,
                          f'Recorded as {recorded}.', source='StudentProfile.citizenship')
    return RuleResult('citizenship', 'Citizenship', FAIL,
                      f'Recorded as {recorded}, which is not Filipino citizenship.',
                      source='StudentProfile.citizenship')


def _enrollment_rule(profile):
    from .constants import BIPSU_SCHOOLS

    school = (profile.school or '').strip()
    if not profile.year_level:
        return RuleResult(
            'enrollment', 'Current College Enrollment', NEEDS_VERIFICATION,
            'No year level on file, so current enrolment cannot be confirmed.',
            source='StudentProfile.year_level', missing=('Year level',))
    if not school:
        return RuleResult(
            'enrollment', 'Current College Enrollment', NEEDS_VERIFICATION,
            f'Enrolled at year {profile.year_level}, but no school is recorded, so CHED '
            'recognition of the institution cannot be confirmed.',
            source='StudentProfile.school', missing=('School',))
    if school in dict(BIPSU_SCHOOLS):
        return RuleResult(
            'enrollment', 'Current College Enrollment', PASS,
            f'Year {profile.year_level} at {school}, a school of BiPSU — a CHED-recognised SUC.',
            source='StudentProfile.school')
    return RuleResult(
        'enrollment', 'Current College Enrollment', NEEDS_VERIFICATION,
        f'Year {profile.year_level} at "{school}", which is not one of BiPSU\'s schools. '
        'CHED recognition of that institution needs checking.',
        source='StudentProfile.school', missing=('CHED recognition of the institution',))


def _first_degree_rule(profile):
    if profile.has_previous_degree is None:
        return RuleResult(
            'first_degree', 'First College Degree', NEEDS_VERIFICATION,
            'Whether the student already holds an undergraduate degree has not been recorded.',
            source='StudentProfile.has_previous_degree', missing=('Previous degree',))
    if profile.has_previous_degree:
        return RuleResult('first_degree', 'First College Degree', FAIL,
                          'Already holds an undergraduate degree, so this is not a first degree.',
                          source='StudentProfile.has_previous_degree')
    return RuleResult('first_degree', 'First College Degree', PASS,
                      'No earlier undergraduate degree on record.',
                      source='StudentProfile.has_previous_degree')


def _maximum_years_rule(profile, today=None):
    started = profile.year_first_enrolled
    if not started:
        return RuleResult(
            'maximum_years', 'Maximum Years of Study', NEEDS_VERIFICATION,
            'The year the student first enrolled has not been recorded, so years used '
            'cannot be counted. Year level alone does not show how long they have been enrolled.',
            source='StudentProfile.year_first_enrolled', missing=('Year first enrolled',))
    today = today or date.today()
    allowed = PROGRAM_YEARS.get(profile.course, STANDARD_PROGRAM_YEARS) + GRACE_YEARS
    used = today.year - started + 1
    if used > allowed:
        return RuleResult(
            'maximum_years', 'Maximum Years of Study', FAIL,
            f'Enrolled since {started} — {used} years used against {allowed} allowed '
            f'({allowed - GRACE_YEARS}-year programme plus a {GRACE_YEARS}-year grace period).',
            source='StudentProfile.year_first_enrolled')
    return RuleResult(
        'maximum_years', 'Maximum Years of Study', PASS,
        f'Enrolled since {started} — {used} of {allowed} allowed years used.',
        source='StudentProfile.year_first_enrolled')


def _other_assistance_rule(profile):
    """Read from the office's own award records first, then the declaration.

    An approved application or link request for a conflicting programme is hard
    evidence. A student who ticked 'has other scholarship' without such a record
    is unresolved rather than disqualified: the system cannot tell whether what
    they hold is government assistance, a private grant, or one-time emergency
    help, which the rules say must not disqualify anyone.
    """
    from .models import Application, ScholarshipLinkRequest

    held = set(
        Application.objects
        .filter(student=profile, status='Approved',
                scholarship__type__in=CONFLICTING_GOVERNMENT_PROGRAMS)
        .values_list('scholarship__type', flat=True)
    )
    held |= set(
        ScholarshipLinkRequest.objects
        .filter(student=profile, status='Approved',
                scholarship_type__in=CONFLICTING_GOVERNMENT_PROGRAMS)
        .values_list('scholarship_type', flat=True)
    )
    if held:
        names = ', '.join(sorted(held))
        return RuleResult(
            'other_assistance', 'Other Government Assistance', FAIL,
            f'Currently holds {names} through this office — ongoing government assistance '
            'that TES cannot be held alongside.',
            source='Application / ScholarshipLinkRequest')
    if profile.has_other_scholarship:
        return RuleResult(
            'other_assistance', 'Other Government Assistance', NEEDS_VERIFICATION,
            'The student declared another scholarship, but no award record identifies it. '
            'Whether it is ongoing government assistance or one-time emergency help '
            '(DSWD AICS, CHED SMART — neither disqualifying) needs checking.',
            source='StudentProfile.has_other_scholarship',
            missing=('Which scholarship the student holds',))
    return RuleResult(
        'other_assistance', 'Other Government Assistance', PASS,
        'No approved TDP, DOST or CHED award on file and none declared.',
        source='Application / StudentProfile.has_other_scholarship')


# ── priority ────────────────────────────────────────────────────────────────

# Free-text priority fields come back with these instead of an empty string when
# the answer was "no". Real records in this system already hold "N/A" in
# disability_type, which read as a disability until this was accounted for.
NEGATIVE_ANSWERS = frozenset({'n/a', 'na', 'none', 'no', 'wala', '-', '--', 'nil', 'n.a.'})


def _stated(value):
    """The value if it is a real answer, else '' — 'N/A' means no, not unknown."""
    text = (value or '').strip()
    return '' if text.casefold() in NEGATIVE_ANSWERS else text


def _priority_signals(profile, application):
    """(confirmed markers, unknown signals) for the Priority 1 groups."""
    markers, unknown = [], []

    if profile.is_listahanan_household is True:
        markers.append('Listahanan household')
    elif profile.is_listahanan_household is None:
        # 4Ps stands in only when Listahanan itself is unrecorded.
        if profile.is_4ps_beneficiary is True:
            markers.append('4Ps beneficiary')
        elif profile.is_4ps_beneficiary is None:
            unknown.append('Listahanan / 4Ps listing')

    if application is not None and application.is_solo_parent_dependent:
        markers.append('Solo parent dependent')
    elif application is None:
        unknown.append('Solo parent status')

    ip_group = _stated(profile.indigenous_group)
    if not ip_group and application is not None:
        ip_group = _stated(application.indigenous_people_group)
    if ip_group:
        markers.append(f'ICC/IP ({ip_group})')

    if profile.is_pwd:
        markers.append('PWD')
    elif application is not None and _stated(application.disability_type):
        markers.append(f'PWD ({_stated(application.disability_type)})')

    return markers, unknown


def _per_capita_income(profile):
    """(per-capita income, state, missing fields).

    family_income defaults to 0.0, so zero is read as 'not entered'. Treating it
    as a real income would rank a student with no data on file as the poorest
    applicant in the list.
    """
    missing = []
    income = profile.family_income
    if not income or income <= 0:
        missing.append('Household income')
    size = profile.household_size
    if not size or size <= 0:
        missing.append('Household size')
    if missing:
        return None, NEEDS_VERIFICATION_LABEL, missing
    return round(income / size, 2), VERIFIED, []


# ── the evaluation ──────────────────────────────────────────────────────────

def evaluate(profile, application=None, today=None):
    """Run every rule against one student. Reads only; never writes, never guesses."""
    if application is None:
        application = profile.tes_applications.order_by('-submitted_at').first()

    rules = [
        _citizenship_rule(profile),
        _enrollment_rule(profile),
        _first_degree_rule(profile),
        _maximum_years_rule(profile, today=today),
        _other_assistance_rule(profile),
    ]

    if any(r.failed for r in rules):
        status = NOT_ELIGIBLE
    elif any(r.unverified for r in rules):
        status = FOR_VERIFICATION
    else:
        status = ELIGIBLE

    markers, unknown_signals = _priority_signals(profile, application)
    per_capita, income_state, income_missing = _per_capita_income(profile)

    if markers:
        priority = PRIORITY_1
    elif unknown_signals:
        # No confirmed Priority 1 group, but the deciding list was never checked.
        priority = PRIORITY_UNDETERMINED
    else:
        priority = PRIORITY_2

    missing = []
    for rule in rules:
        missing.extend(rule.missing)
    # An unchecked priority signal only matters while it could still change the
    # answer. Once a Priority 1 group is confirmed, the others cannot move the
    # student anywhere, so listing them would send the office chasing paperwork
    # that changes nothing.
    if priority != PRIORITY_1:
        missing.extend(unknown_signals)
    missing.extend(income_missing)

    return Evaluation(
        profile=profile,
        application=application,
        rules=rules,
        status=status,
        priority=priority,
        priority_markers=markers,
        per_capita_income=per_capita,
        income_rank_state=income_state,
        missing=list(dict.fromkeys(missing)),   # de-duplicated, order kept
    )


def rank(profiles, today=None):
    """Evaluate and order a set of students, numbering them from 1.

    Everyone appears, including students whose data is incomplete — they are
    marked For Verification rather than dropped, so the office can see who still
    needs chasing instead of quietly losing them.
    """
    evaluations = [evaluate(p, today=today) for p in profiles]
    evaluations.sort(key=lambda e: e.sort_key)
    for position, evaluation in enumerate(evaluations, start=1):
        evaluation.rank = position
    return evaluations
