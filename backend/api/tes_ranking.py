from dataclasses import dataclass
from datetime import date

PASS = 'PASS'
FAIL = 'FAIL'

ELIGIBLE = 'Eligible'
NOT_ELIGIBLE = 'Not Eligible'

PRIORITY_1 = 'Priority 1'
PRIORITY_2 = 'Priority 2'

STANDARD_PROGRAM_YEARS = 4
GRACE_YEARS = 1
PROGRAM_YEARS = {}

CONFLICTING_GOVERNMENT_PROGRAMS = ('TDP', 'DOST', 'CHED')

NEGATIVE_ANSWERS = frozenset({'n/a', 'na', 'none', 'no', 'wala', '-', '--', 'nil', 'n.a.'})


def _stated(value):
    text = (value or '').strip()
    return '' if text.casefold() in NEGATIVE_ANSWERS else text


@dataclass(frozen=True)
class RuleResult:
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
        return [r for r in self.rules if r.failed]

    @property
    def reason(self):
        return '; '.join(r.label for r in self.failed_rules)

    @property
    def sort_key(self):
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


def _pending_declarations(profiles):
    from .models import ScholarshipLinkRequest

    pending = {}
    rows = (ScholarshipLinkRequest.objects
            .filter(student__in=profiles, status='Pending')
            .values_list('student_id', 'scholarship_type'))
    for student_id, scholarship_type in rows:
        pending.setdefault(student_id, set()).add(scholarship_type)
    return pending


def unanswered_on_record(profile):
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


def missing_answers(profile, pending=None):
    gaps = list(unanswered_on_record(profile))

    if pending is None:
        pending = _pending_declarations([profile.pk])
    undecided = pending.get(profile.pk)
    if undecided:
        gaps.append('A decision on ' + ', '.join(sorted(undecided)))

    return tuple(dict.fromkeys(gaps))


def screen(profiles):
    profiles = list(profiles)
    pending = _pending_declarations(profiles)
    complete, incomplete = [], []
    for profile in profiles:
        (incomplete if missing_answers(profile, pending=pending) else complete).append(profile)
    return complete, incomplete


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


def _priority_signals(profile):
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


def _per_capita_income(profile):
    return round(profile.family_income / profile.household_size, 2)


def evaluate(profile, today=None):
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
    complete, _ = screen(profiles)
    evaluations = [evaluate(p, today=today) for p in complete]
    evaluations.sort(key=lambda e: e.sort_key)
    for position, evaluation in enumerate(evaluations, start=1):
        evaluation.rank = position
    return evaluations
