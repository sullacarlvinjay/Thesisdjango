"""The Tertiary Education Subsidy eligibility rules.

Rule-based filtering, not a model. Five rules decide eligibility; priority
markers then order the people who are already eligible, because the fund runs
out before the list does.

The distinction the module is built around: a blank field is an unknown, not a
"no". An applicant whose record cannot answer a question is set aside for the
office to chase rather than judged on what is absent — see
:func:`unanswered_on_record`.
"""

from dataclasses import dataclass
from datetime import date
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import StudentProfile

PASS = 'PASS'
FAIL = 'FAIL'

ELIGIBLE = 'Eligible'
NOT_ELIGIBLE = 'Not Eligible'

PRIORITY_1 = 'Priority 1'
PRIORITY_2 = 'Priority 2'

STANDARD_PROGRAM_YEARS = 4
GRACE_YEARS = 1
PROGRAM_YEARS: dict[str, int] = {}

CONFLICTING_GOVERNMENT_PROGRAMS = ('TDP', 'DOST', 'CHED')

NEGATIVE_ANSWERS = frozenset({'n/a', 'na', 'none', 'no', 'wala', '-', '--', 'nil', 'n.a.'})


def _stated(value: Any) -> str:
    """Return a real answer, or '' for one of the ways people write "none".

    Forms collect free text, and "N/A", "wala", "-" and an empty box all mean
    the same thing: the person is not claiming this. Treating them as text
    would award a priority marker for an indigenous group literally named
    "None".
    """
    text = (value or '').strip()
    return '' if text.casefold() in NEGATIVE_ANSWERS else text


@dataclass(frozen=True)
class RuleResult:
    """One eligibility rule's verdict on one applicant.

    Frozen, because a verdict is evidence: it records what was checked, what
    the answer was, and which field it came from, so a decision can be
    explained months later without re-running anything.

    Attributes:
        key: stable identifier, e.g. ``'citizenship'``.
        label: the rule's name as the office reads it.
        verdict: :data:`PASS` or :data:`FAIL`.
        detail: the sentence shown to whoever asks why.
        source: the field the answer was read from.
    """
    key: str
    label: str
    verdict: str
    detail: str
    source: str = ''

    @property
    def passed(self) -> bool:
        """Whether this rule was satisfied."""
        return self.verdict == PASS

    @property
    def failed(self) -> bool:
        """Whether this rule refused the applicant."""
        return self.verdict == FAIL


@dataclass
class Evaluation:
    """The full verdict on one applicant: every rule, plus a ranking.

    Eligibility and priority are separate questions. A rule failing makes
    someone ineligible; priority markers only order the people who are
    already eligible, which is why both are carried rather than collapsed
    into a single score.
    """
    profile: 'StudentProfile'
    rules: list[RuleResult]
    status: str
    priority: str
    priority_markers: list[str]
    per_capita_income: float | None = None
    rank: int | None = None

    @property
    def student_name(self) -> str:
        """The applicant's name, from the profile or the account."""
        return self.profile.full_name or self.profile.user.get_full_name()

    @property
    def student_id(self) -> str:
        """The applicant's student number."""
        return self.profile.student_id

    @property
    def eligible(self) -> bool:
        """Whether every rule passed."""
        return self.status == ELIGIBLE

    @property
    def recommendation(self) -> str:
        """The verdict in the words the office uses.

        Three outcomes, not two: an eligible applicant carrying a priority marker
        is distinguished from one who merely qualifies, because the fund runs out
        before the list does.
        """
        if self.status == NOT_ELIGIBLE:
            return 'Not Recommended'
        return 'High Priority' if self.priority == PRIORITY_1 else 'Recommended'

    def rule(self, key: str) -> RuleResult | None:
        """The result for one rule key, or ``None`` if it was not run."""
        for r in self.rules:
            if r.key == key:
                return r
        return None

    @property
    def failed_rules(self) -> list[RuleResult]:
        """Every rule that refused this applicant."""
        return [r for r in self.rules if r.failed]

    @property
    def reason(self) -> str:
        """Why this applicant was refused, as one sentence.

        Empty for an eligible applicant. Built from the rules that failed rather
        than written separately, so the reason cannot drift from the decision.
        """
        return '; '.join(r.label for r in self.failed_rules)

    @property
    def sort_key(self) -> tuple:
        """Ranking order: eligibility, then priority, then need.

        Eligible before ineligible, Priority 1 before Priority 2, then lowest
        per-capita income first — poverty is the tie-break the programme is for.
        More priority markers come next, and surname last so that two applicants
        who are equal on every count still land in a stable, checkable order.
        """
        return (
            0 if self.status == ELIGIBLE else 1,
            0 if self.priority == PRIORITY_1 else 1,
            self.per_capita_income,
            -len(self.priority_markers),
            (self.profile.user.last_name or '').lower(),
        )


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


def _pending_declarations(profiles: Sequence[Any]) -> dict[int, set[str]]:
    """Scholarship types each applicant has declared but nobody has decided.

    An undecided declaration is neither held nor not held. Ranking someone
    while one is outstanding risks recommending TES to a person who turns out
    to hold a conflicting award, so these are treated as a gap in the record
    rather than as a "no".

    Args:
        profiles: the profiles (or their primary keys) being screened.

    Returns:
        ``{profile_id: {scholarship_type, ...}}`` for those with any pending.
    """
    from .models import ScholarshipLinkRequest

    pending: dict[int, set[str]] = {}
    rows = (ScholarshipLinkRequest.objects
            .filter(student__in=profiles, status='Pending')
            .values_list('student_id', 'scholarship_type'))
    for student_id, scholarship_type in rows:
        pending.setdefault(student_id, set()).add(scholarship_type)
    return pending


def unanswered_on_record(profile: 'StudentProfile') -> tuple[str, ...]:
    """Questions this applicant's record cannot answer yet.

    Every rule below reads a stored field. A blank field is not a "no" — it is
    an unknown, and the difference matters when the output decides who gets
    money. This lists the unknowns so the applicant can be set aside rather
    than judged on absent data.

    Zero and negative income or household size count as unanswered too: they
    are placeholders, and dividing by a household of nobody is not a per-capita
    income. A school outside the CHED-recognised list is reported as such
    rather than silently failing the enrolment rule.

    Returns:
        A tuple of human-readable gaps, empty when the record is complete.
    """
    from .constants import BIPSU_SCHOOLS

    gaps = []
    for attribute, label in REQUIRED_ANSWERS:
        value = getattr(profile, attribute, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            gaps.append(label)

    if profile.family_income is not None and profile.family_income <= 0:
        gaps.append('Household income')
    if profile.household_size is not None and profile.household_size <= 0:
        gaps.append('Household size')

    school = (profile.school or '').strip()
    if not school:
        gaps.append('School')
    elif school not in dict(BIPSU_SCHOOLS):
        gaps.append(f'CHED recognition of "{school}"')

    if profile.is_listahanan_household is None and profile.is_4ps_beneficiary is None:
        gaps.append('Listahanan / 4Ps listing')

    return tuple(dict.fromkeys(gaps))


def missing_answers(profile: 'StudentProfile',
                    pending: dict[int, set[str]] | None = None,
                    ) -> tuple[str, ...]:
    """Every gap in one applicant's record, including undecided declarations.

    :func:`unanswered_on_record` covers the stored fields; this adds the
    declarations still waiting on the office.

    Args:
        profile: the applicant.
        pending: a prepared mapping from :func:`_pending_declarations`. Pass it
            when screening many applicants, or one query runs per person.
    """
    gaps = list(unanswered_on_record(profile))

    if pending is None:
        pending = _pending_declarations([profile.pk])
    undecided = pending.get(profile.pk)
    if undecided:
        gaps.append('A decision on ' + ', '.join(sorted(undecided)))

    return tuple(dict.fromkeys(gaps))


def screen(profiles: Iterable['StudentProfile'],
           ) -> tuple[list['StudentProfile'], list['StudentProfile']]:
    """Split applicants into those who can be judged and those who cannot.

    Returns:
        ``(complete, incomplete)``. Nothing is discarded — the incomplete list
        is what the office chases, and reporting it is the point. A recommender
        that silently dropped these would look decisive and be wrong.
    """
    profiles = list(profiles)
    pending = _pending_declarations(profiles)
    complete: list[StudentProfile] = []
    incomplete: list[StudentProfile] = []
    for profile in profiles:
        (incomplete if missing_answers(profile, pending=pending) else complete).append(profile)
    return complete, incomplete


def _citizenship_rule(profile: 'StudentProfile') -> RuleResult:
    """Filipino citizenship, as recorded on the profile."""
    recorded = _stated(profile.citizenship)
    if recorded.casefold() in ('filipino', 'filipino citizen', 'philippine', 'pilipino'):
        return RuleResult('citizenship', 'Citizenship', PASS,
                          f'Recorded as {recorded}.', source='StudentProfile.citizenship')
    return RuleResult('citizenship', 'Citizenship', FAIL,
                      f'Recorded as {recorded or "not Filipino"}, which is not '
                      'Filipino citizenship.',
                      source='StudentProfile.citizenship')


def _enrollment_rule(profile: 'StudentProfile') -> RuleResult:
    """Current enrolment at a CHED-recognised SUC.

    Always passes at this point: :func:`unanswered_on_record` has already
    rejected a record whose school is missing or outside the recognised list,
    so anything reaching here is enrolled somewhere that qualifies. The rule
    still exists so the verdict names the school it accepted.
    """
    return RuleResult(
        'enrollment', 'Current College Enrollment', PASS,
        f'Year {profile.year_level} at {profile.school}, a school of BiPSU — '
        'a CHED-recognised SUC.',
        source='StudentProfile.school')


def _first_degree_rule(profile: 'StudentProfile') -> RuleResult:
    """TES is for a first undergraduate degree only."""
    if profile.has_previous_degree:
        return RuleResult('first_degree', 'First College Degree', FAIL,
                          'Already holds an undergraduate degree, so this is not a first degree.',
                          source='StudentProfile.has_previous_degree')
    return RuleResult('first_degree', 'First College Degree', PASS,
                      'No earlier undergraduate degree on record.',
                      source='StudentProfile.has_previous_degree')


def _maximum_years_rule(profile: 'StudentProfile',
                        today: date | None = None) -> RuleResult:
    """Whether the applicant is still inside the allowed years of study.

    The programme length plus a one-year grace period. ``PROGRAM_YEARS`` holds
    the exceptions; anything not listed is assumed to be the standard four.
    """
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


def _other_assistance_rule(profile: 'StudentProfile') -> RuleResult:
    """No other government grant may be held alongside TES.

    Both the awards this office recorded and the ones the applicant declared
    are checked, because a scholar can hold a TDP award granted elsewhere that
    only exists here as a declaration.
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


def _priority_signals(profile: 'StudentProfile') -> list[str]:
    """The grounds, if any, for ranking this applicant ahead of others.

    Listahanan listing is the primary measure; 4Ps is read only when the
    Listahanan answer is unknown, because the two overlap and counting both
    would double-weight the same household.
    """
    markers = []

    if profile.is_listahanan_household is True:
        markers.append('Listahanan household')
    elif profile.is_listahanan_household is None and profile.is_4ps_beneficiary is True:
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


def _per_capita_income(profile: 'StudentProfile') -> float:
    """Household income divided by household size, to two places."""
    return round(profile.family_income / profile.household_size, 2)


def evaluate(profile: 'StudentProfile',
             today: date | None = None) -> Evaluation:
    """Judge one applicant against every rule.

    Args:
        profile: a complete profile. Screen first — this refuses an incomplete
            one rather than reading a blank field as a "no".
        today: the date to measure years of study against. Defaults to today;
            supplying it makes the result reproducible in tests.

    Returns:
        An :class:`Evaluation` carrying every verdict and its reason.

    Raises:
        ValueError: if the record still has unanswered questions.
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


def rank(profiles: Iterable['StudentProfile'],
         today: date | None = None) -> list[Evaluation]:
    """Screen, evaluate and order a set of applicants.

    Applicants with incomplete records are set aside rather than ranked; use
    :func:`screen` to see who they are and what is missing.

    Returns:
        Evaluations in recommendation order, each with ``rank`` filled in.
    """
    complete, _ = screen(profiles)
    evaluations = [evaluate(p, today=today) for p in complete]
    evaluations.sort(key=lambda e: e.sort_key)
    for position, evaluation in enumerate(evaluations, start=1):
        evaluation.rank = position
    return evaluations
