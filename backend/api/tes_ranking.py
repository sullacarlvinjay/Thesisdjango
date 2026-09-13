"""Rule-based TES recommender: screening, eligibility, priority and ranking.

Nothing in this system awards TES. UniFAST does, outside the portal, so what
the SDSO produces here is a **recommendation** — who the university would put
forward, and the reason behind every line of it. That is why nothing in this
module writes to the database: it reads the student record the office already
holds and states what the rules make of it.

**TES is decided on complete records only.** A student whose record still has an
unanswered question is not ranked, not failed, and not shown: :func:`screen`
removes them before a single rule runs, and the page reports how many were held
back as a count and nothing more. Two consequences the office should know it is
choosing:

  * A student can be missing one answer and be invisible on this page, with
    nothing on it saying which answer or whose. The count is the only trace.
  * The gap is not visible where it is fixable either. Nothing here tells the
    student, and My Profile does not flag an unanswered question — so a record
    stays incomplete until somebody thinks to look at it.

The screen is deliberately the only place incompleteness is handled. Past the
screen every rule is a straight PASS or FAIL, because every field it reads has
an answer by then; a rule that still had to describe a third outcome would mean
the screen had missed something.

What counts as an unanswered question is :data:`REQUIRED_ANSWERS` plus the two
states in :func:`missing_answers` that are not a blank field at all — a school
this system cannot recognise, and a declared scholarship the office has not
decided on. Both leave a rule unable to run rather than able to fail, which is
the same reason a blank field does.

Field mapping (requirement -> the field actually used). Every one of them is on
the student's own record, collected at registration and correctable on My
Profile, because there is no TES application form here to ask twice:

    Citizenship             StudentProfile.citizenship
    Enrolled / CHED-recog.  StudentProfile.year_level, .school
    First degree            StudentProfile.has_previous_degree
    Maximum years           StudentProfile.year_first_enrolled + PROGRAM_YEARS
    Other gov. assistance   Application / ScholarshipLinkRequest rows
    Listahanan              StudentProfile.is_listahanan_household
    4Ps (fallback)          StudentProfile.is_4ps_beneficiary
    Solo parent dependent   StudentProfile.is_solo_parent_dependent
    ICC / IP                StudentProfile.indigenous_group
    PWD                     StudentProfile.disability_type
    Household income        StudentProfile.family_income
    Household size          StudentProfile.household_size
"""
from dataclasses import dataclass
from datetime import date

PASS = 'PASS'
FAIL = 'FAIL'

ELIGIBLE = 'Eligible'
NOT_ELIGIBLE = 'Not Eligible'

PRIORITY_1 = 'Priority 1'
PRIORITY_2 = 'Priority 2'

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

# Free-text priority fields come back with these instead of an empty string when
# the answer was "no". Real records in this system already hold "N/A" in
# disability_type, which read as a disability until this was accounted for.
NEGATIVE_ANSWERS = frozenset({'n/a', 'na', 'none', 'no', 'wala', '-', '--', 'nil', 'n.a.'})


def _stated(value):
    """The value if it is a real answer, else '' — 'N/A' means no, not unknown."""
    text = (value or '').strip()
    return '' if text.casefold() in NEGATIVE_ANSWERS else text


@dataclass(frozen=True)
class RuleResult:
    """One eligibility rule, its verdict, and why."""
    key: str
    label: str
    verdict: str
    detail: str
    source: str = ''

    @property
    def passed(self):
        return self.verdict == PASS

    @property
    def failed(self):
        return self.verdict == FAIL


@dataclass
class Evaluation:
    """Everything the office needs to see, and to defend, for one student."""
    profile: object
    rules: list
    status: str
    priority: str
    priority_markers: list
    per_capita_income: float = None
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
    def recommendation(self):
        """The one-line verdict shown in the Recommendation column."""
        if self.status == NOT_ELIGIBLE:
            return 'Not Recommended'
        return 'High Priority' if self.priority == PRIORITY_1 else 'Recommended'

    def rule(self, key):
        for r in self.rules:
            if r.key == key:
                return r
        return None

    @property
    def failed_rules(self):
        """The rules behind a Not Eligible verdict, for the Reason column."""
        return [r for r in self.rules if r.failed]

    @property
    def reason(self):
        """Why this student is not recommended, or '' when they are."""
        return '; '.join(r.label for r in self.failed_rules)

    @property
    def sort_key(self):
        """Eligibility, then priority, then per-capita income, then markers.

        Every term is known for every row on the list — that is what the screen
        buys. Income is a plain ascending number here because there is no longer
        such a thing as a ranked student whose income was never entered.
        """
        return (
            0 if self.status == ELIGIBLE else 1,
            0 if self.priority == PRIORITY_1 else 1,
            self.per_capita_income,
            -len(self.priority_markers),
            (self.profile.user.last_name or '').lower(),
        )


# ── the screen ──────────────────────────────────────────────────────────────

# Every answer a rule needs, and the name the office would know it by. Read in
# the order the rules use them so a listing of what a record lacks follows the
# same order as the page.
REQUIRED_ANSWERS = (
    ('citizenship', 'Citizenship'),
    ('year_level', 'Year level'),
    ('has_previous_degree', 'Whether they already hold a degree'),
    ('year_first_enrolled', 'Year first enrolled'),
    ('is_solo_parent_dependent', 'Solo parent status'),
    ('disability_type', 'Disability (or NO for none)'),
    ('household_size', 'Household size'),
    ('family_income', 'Household income'),
)


def _pending_declarations(profiles):
    """{student pk -> the scholarship types they declared and nobody ruled on}.

    One query for the whole cohort. Asking per student turned the screen into a
    query per row, which is the cost this page was already paying elsewhere and
    had no reason to pay again.
    """
    from .models import ScholarshipLinkRequest

    pending = {}
    rows = (ScholarshipLinkRequest.objects
            .filter(student__in=profiles, status='Pending')
            .values_list('student_id', 'scholarship_type'))
    for student_id, scholarship_type in rows:
        pending.setdefault(student_id, set()).add(scholarship_type)
    return pending


def unanswered_on_record(profile):
    """The gaps readable from the record in hand, without asking the database.

    Split out from :func:`missing_answers` so :func:`evaluate` can hold itself
    to its own contract for free — everything here is an attribute read, and
    only the declaration check below costs a query.
    """
    from .constants import BIPSU_SCHOOLS

    gaps = []
    for attribute, label in REQUIRED_ANSWERS:
        value = getattr(profile, attribute, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            gaps.append(label)

    # Zero is how an untouched numeric field looks, not a household of nobody
    # earning nothing. family_income defaults to 0.0, so reading it as a real
    # income would rank a student with no data on file as the poorest applicant.
    if profile.family_income is not None and profile.family_income <= 0:
        gaps.append('Household income')
    if profile.household_size is not None and profile.household_size <= 0:
        gaps.append('Household size')

    # Not a blank field: a school this system cannot place. CHED recognition of
    # it cannot be confirmed from here, so the enrolment rule has nothing to
    # decide on either way.
    school = (profile.school or '').strip()
    if not school:
        gaps.append('School')
    elif school not in dict(BIPSU_SCHOOLS):
        gaps.append(f'CHED recognition of "{school}"')

    # Listahanan decides priority, and 4Ps stands in only when Listahanan itself
    # was never checked. One of the two has to have been answered.
    if profile.is_listahanan_household is None and profile.is_4ps_beneficiary is None:
        gaps.append('Listahanan / 4Ps listing')

    return tuple(dict.fromkeys(gaps))   # de-duplicated, order kept


def missing_answers(profile, pending=None):
    """What this record still lacks before TES rules can be run on it.

    Empty means the student is ranked. Anything in it means they are held back
    from the list entirely — see the module docstring for what that costs.

    ``pending`` is the cohort-wide map from :func:`_pending_declarations`; left
    out, this asks for the one student, which is what a caller screening a
    single record wants.
    """
    gaps = list(unanswered_on_record(profile))

    # Not a blank field: a scholarship the student declared that nobody has
    # ruled on. Until it is reviewed the system cannot tell ongoing government
    # assistance from one-time emergency help, so the conflict rule can neither
    # pass nor fail.
    if pending is None:
        pending = _pending_declarations([profile.pk])
    undecided = pending.get(profile.pk)
    if undecided:
        gaps.append('A decision on ' + ', '.join(sorted(undecided)))

    return tuple(dict.fromkeys(gaps))   # de-duplicated, order kept


def screen(profiles):
    """Split students into those TES can be decided for and those it cannot.

    Returns ``(complete, incomplete)``. Only the first list is evaluated; the
    second exists so the page can say how many students it is not showing.
    """
    profiles = list(profiles)
    pending = _pending_declarations(profiles)
    complete, incomplete = [], []
    for profile in profiles:
        (incomplete if missing_answers(profile, pending=pending) else complete).append(profile)
    return complete, incomplete


# ── individual rules ────────────────────────────────────────────────────────
#
# Past the screen every field these read has an answer, so each is a straight
# PASS or FAIL. None of them re-checks for a blank: if one had to, the screen
# above would be the thing to fix.

def _citizenship_rule(profile):
    recorded = _stated(profile.citizenship)
    if recorded.casefold() in ('filipino', 'filipino citizen', 'philippine', 'pilipino'):
        return RuleResult('citizenship', 'Citizenship', PASS,
                          f'Recorded as {recorded}.', source='StudentProfile.citizenship')
    return RuleResult('citizenship', 'Citizenship', FAIL,
                      f'Recorded as {recorded or "not Filipino"}, which is not '
                      'Filipino citizenship.',
                      source='StudentProfile.citizenship')


def _enrollment_rule(profile):
    return RuleResult(
        'enrollment', 'Current College Enrollment', PASS,
        f'Year {profile.year_level} at {profile.school}, a school of BiPSU — '
        'a CHED-recognised SUC.',
        source='StudentProfile.school')


def _first_degree_rule(profile):
    if profile.has_previous_degree:
        return RuleResult('first_degree', 'First College Degree', FAIL,
                          'Already holds an undergraduate degree, so this is not a first degree.',
                          source='StudentProfile.has_previous_degree')
    return RuleResult('first_degree', 'First College Degree', PASS,
                      'No earlier undergraduate degree on record.',
                      source='StudentProfile.has_previous_degree')


def _maximum_years_rule(profile, today=None):
    started = profile.year_first_enrolled
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
    """Read from the office's own award records.

    An approved application or link request for a conflicting programme is hard
    evidence. A declaration nobody has ruled on yet never reaches this rule —
    the screen holds that student back, because the system cannot tell whether
    what they hold is government assistance, a private grant, or one-time
    emergency help, which the rules say must not disqualify anyone.
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
    return RuleResult(
        'other_assistance', 'Other Government Assistance', PASS,
        'No approved TDP, DOST or CHED award on file and none declared.',
        source='Application / ScholarshipLinkRequest')


# ── priority ────────────────────────────────────────────────────────────────

def _priority_signals(profile):
    """The Priority 1 groups this student is confirmed to be in."""
    markers = []

    if profile.is_listahanan_household is True:
        markers.append('Listahanan household')
    elif profile.is_listahanan_household is None and profile.is_4ps_beneficiary is True:
        # 4Ps stands in only when Listahanan itself is unrecorded.
        markers.append('4Ps beneficiary')

    if profile.is_solo_parent_dependent is True:
        markers.append('Solo parent dependent')

    ip_group = _stated(profile.indigenous_group)
    if ip_group:
        markers.append(f'ICC/IP ({ip_group})')

    disability = _stated(profile.disability_type)
    if disability:
        markers.append(f'PWD ({disability})')

    return markers


def _per_capita_income(profile):
    """Household income over household size. Both are guaranteed by the screen."""
    return round(profile.family_income / profile.household_size, 2)


# ── the evaluation ──────────────────────────────────────────────────────────

def evaluate(profile, today=None):
    """Run every rule against one student whose record is complete.

    Reads only; never writes, never guesses. Passing a profile that has not been
    through :func:`screen` is a caller error: the rules assume every answer is
    there, so this says so plainly rather than letting one of them fall over on
    an arithmetic operand somewhere further down.
    """
    gaps = unanswered_on_record(profile)
    if gaps:
        raise ValueError(
            f'{profile} has not been screened — still unanswered: {", ".join(gaps)}. '
            'Call screen() or rank(), which skip a record like this rather than '
            'ranking it on what is not there.')

    rules = [
        _citizenship_rule(profile),
        _enrollment_rule(profile),
        _first_degree_rule(profile),
        _maximum_years_rule(profile, today=today),
        _other_assistance_rule(profile),
    ]

    status = NOT_ELIGIBLE if any(r.failed for r in rules) else ELIGIBLE
    markers = _priority_signals(profile)

    return Evaluation(
        profile=profile,
        rules=rules,
        status=status,
        priority=PRIORITY_1 if markers else PRIORITY_2,
        priority_markers=markers,
        per_capita_income=_per_capita_income(profile),
    )


def rank(profiles, today=None):
    """Evaluate and order the students whose records are complete, from 1.

    Screens first, so a caller can hand this the whole cohort. Students held
    back are simply absent from the result — :func:`screen` is the way to find
    out how many there were.
    """
    complete, _ = screen(profiles)
    evaluations = [evaluate(p, today=today) for p in complete]
    evaluations.sort(key=lambda e: e.sort_key)
    for position, evaluation in enumerate(evaluations, start=1):
        evaluation.rank = position
    return evaluations
