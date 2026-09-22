"""The BiPSU Staff Scholarship qualification rules.

Three outcomes rather than two. Alongside qualified and not qualified there is
*for verification*, for an application whose rules could not be run because the
record is incomplete. That is not a refusal, and an applicant must not be
turned down over a question nobody asked them.

Which rules apply at all depends on whether the applicant is the employee or
their dependent, so that is settled first.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ApplicantRecord

PASS = 'PASS'
FAIL = 'FAIL'
NEEDS_VERIFICATION = 'NEEDS VERIFICATION'

QUALIFIED = 'Qualified'
NOT_QUALIFIED = 'Not Qualified'
FOR_VERIFICATION = 'For Verification'

STAFF = 'Employee'
DEPENDENT = 'Dependent'
UNSTATED = 'Not stated'

PERMANENT_APPOINTMENTS = ('Regular', 'Permanent')


@dataclass(frozen=True)
class RuleResult:
    """One qualification's verdict on one staff application.

    Carries a third outcome the TES rules do not need: ``NEEDS VERIFICATION``,
    for a rule that could not be run because the record is incomplete. That is
    not the same as failing, and an applicant must not be refused for a
    question nobody asked them.

    Attributes:
        key: stable identifier, e.g. ``'permanent'``.
        label: the qualification as the office words it.
        verdict: :data:`PASS`, :data:`FAIL` or :data:`NEEDS_VERIFICATION`.
        detail: the sentence explaining the verdict.
        source: the field the answer was read from.
        missing: what the office has to obtain before the rule can be run.
    """
    key: str
    label: str
    verdict: str
    detail: str
    source: str = ''
    missing: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """Whether this qualification was met."""
        return self.verdict == PASS

    @property
    def failed(self) -> bool:
        """Whether this qualification refused the applicant."""
        return self.verdict == FAIL

    @property
    def unverified(self) -> bool:
        """Whether the rule could not be run for want of an answer.

        Distinct from failing: the applicant has not been refused, the office has
        simply not been given what it needs to decide.
        """
        return self.verdict == NEEDS_VERIFICATION


@dataclass
class Evaluation:
    """The full verdict on one staff application.

    Attributes:
        application: the ``ApplicantRecord`` judged.
        standing: :data:`STAFF`, :data:`DEPENDENT` or :data:`UNSTATED`, which
            decides which qualifications apply at all.
        rules: every verdict, in the order they were run.
        status: :data:`QUALIFIED`, :data:`NOT_QUALIFIED` or
            :data:`FOR_VERIFICATION`.
        missing: what the office must obtain, collected from the rules.
        rank: position in the ranked list, filled in by :func:`rank`.
    """
    application: 'ApplicantRecord'
    standing: str
    rules: list[RuleResult]
    status: str
    missing: list[str] = field(default_factory=list)
    rank: int | None = None

    @property
    def applicant_name(self) -> str:
        """The applicant's name as the application records it."""
        return self.application.full_name

    @property
    def qualified(self) -> bool:
        """Whether every qualification was met outright."""
        return self.status == QUALIFIED

    @property
    def needs_verification(self) -> bool:
        """Whether a decision is waiting on missing information."""
        return self.status == FOR_VERIFICATION

    @property
    def refusals(self) -> list[RuleResult]:
        """Every qualification this application failed outright.

        What the office reads back when asked why somebody was not
        recommended. A rule that could not be run is not in here: that is
        missing information, not a refusal.
        """
        return [r for r in self.rules if r.failed]

    @property
    def recommendation(self) -> str:
        """The verdict in the words the office uses.

        Eligibility, not a recommendation. The programme has no merit test and
        no quota to rank against: an employee is on the list for holding a
        permanent appointment, and saying "Recommended" would claim a judgment
        nobody made.
        """
        if self.status == NOT_QUALIFIED:
            return 'Not Eligible'
        if self.status == FOR_VERIFICATION:
            return 'For Verification'
        return 'Eligible'

    @property
    def applied(self) -> bool:
        """Whether an application backs this entry, or only the roster.

        An employee reaches the list either way. This is what lets the office
        tell somebody who asked for the scholarship from somebody who is
        merely eligible for it.
        """
        return getattr(self.application, 'applied', True)

    def rule(self, key: str) -> RuleResult | None:
        """The result for one rule key, or ``None`` if it was not run."""
        for r in self.rules:
            if r.key == key:
                return r
        return None

    @property
    def permanent_verdict(self) -> str:
        """The appointment rule's verdict, for the ranking table."""
        return self._verdict_of('permanent')

    @property
    def baccalaureate_verdict(self) -> str:
        """The prior-degree rule's verdict, for the ranking table."""
        return self._verdict_of('baccalaureate')

    def _verdict_of(self, key: str) -> str:
        """One rule's verdict, or unverified where the rule never ran.

        A rule that did not run is not a pass: the ranking table would show a
        blank cell as if the qualification had been checked.
        """
        found = self.rule(key)
        return found.verdict if found is not None else NEEDS_VERIFICATION

    @property
    def sort_key(self) -> tuple:
        """Ranking order: qualified first, then by name.

        There is no score to sort on. The qualifications are pass or fail, so the
        list groups by status and orders alphabetically within each group, which
        is stable and is what the office reads down.
        """
        status_rank = {QUALIFIED: 0, FOR_VERIFICATION: 1, NOT_QUALIFIED: 2}[self.status]
        return (status_rank, (self.application.full_name or '').lower())


def _standing_rule(application: 'ApplicantRecord') -> tuple[str, RuleResult]:
    """Decide whether this is an employee applying or their dependent.

    Everything else depends on the answer, so it is settled first. Both flags
    set is treated as unverified rather than picking one: an employee is
    judged on their own appointment and a dependent on their parent's, and
    guessing would apply the wrong test.

    Returns:
        ``(standing, RuleResult)``.
    """
    staff = bool(application.is_nsu_staff)
    dependent = bool(application.is_nsu_dependent)

    if staff and dependent:
        return STAFF, RuleResult(
            'standing', 'Employee or dependent', NEEDS_VERIFICATION,
            'The application is marked both employee and dependent. Only one '
            'of the two can be true, and the qualifications differ — an '
            'employee is judged on their own appointment, a dependent on their '
            "parent's.",
            source='is_nsu_staff / is_nsu_dependent',
            missing=('Whether the applicant is the employee or their dependent',))
    if staff:
        return STAFF, RuleResult(
            'standing', 'Employee or dependent', PASS,
            'Applying as a member of the faculty or staff.',
            source='is_nsu_staff')
    if dependent:
        return DEPENDENT, RuleResult(
            'standing', 'Employee or dependent', PASS,
            'Applying as the dependent of a member of the faculty or staff.',
            source='is_nsu_dependent')
    return UNSTATED, RuleResult(
        'standing', 'Employee or dependent', NEEDS_VERIFICATION,
        'The application says neither. The programme is open to employees and '
        'to their dependents, and which one this is decides which rules apply.',
        source='is_nsu_staff / is_nsu_dependent',
        missing=('Whether the applicant is the employee or their dependent',))


def _permanent_appointment_rule(application: 'ApplicantRecord',
                                standing: str) -> RuleResult:
    """Whether the appointment behind the claim is permanent.

    Qualification (a) for an employee, (b) for a dependent. For a dependent
    the appointment belongs to the employee they claim through, so the staff
    record is looked up by employee ID — and a missing or unfindable record is
    reported as unverified, because the dependent has not failed anything.
    """
    if standing == STAFF:
        status = (application.employment_status or '').strip()
        if not status:
            return RuleResult(
                'permanent', 'Permanent appointment', NEEDS_VERIFICATION,
                'No appointment status is recorded, so whether it is '
                'permanent cannot be read.',
                source='employment_status',
                missing=('Employment status',))
        if status in PERMANENT_APPOINTMENTS:
            return RuleResult(
                'permanent', 'Permanent appointment', PASS,
                f'Recorded as {status}.', source='employment_status')
        return RuleResult(
            'permanent', 'Permanent appointment', FAIL,
            f'Recorded as {status}. Qualification (a) is open to faculty and '
            'employees with a permanent appointment.',
            source='employment_status')

    if standing == DEPENDENT:
        employee_id = (application.staff_employee_id or '').strip()
        if not employee_id:
            return RuleResult(
                'permanent', "The employee's appointment", NEEDS_VERIFICATION,
                'No employee ID was given for the faculty or staff member this '
                'dependent is claiming through, so their appointment cannot be '
                'looked up.',
                source='staff_employee_id',
                missing=('Employee ID of the faculty or staff member',))
        from .models import StaffProfile
        employee = (StaffProfile.objects
                    .select_related('employment', 'user')
                    .filter(employee_id=employee_id).first())
        if employee is None:
            return RuleResult(
                'permanent', "The employee's appointment", NEEDS_VERIFICATION,
                f'No staff record carries employee ID {employee_id}. The '
                'dependent has not failed the rule — it has not been possible '
                'to run it.',
                source='staff_employee_id',
                missing=(f'A staff record for employee ID {employee_id}',))
        status = (employee.employment_status or '').strip()
        if not status:
            return RuleResult(
                'permanent', "The employee's appointment", NEEDS_VERIFICATION,
                f'{employee.user.get_full_name()} is on file, but their '
                'appointment status is blank.',
                source='StaffProfile.employment_status',
                missing=(f'Appointment status for employee ID {employee_id}',))
        if status in PERMANENT_APPOINTMENTS:
            return RuleResult(
                'permanent', "The employee's appointment", PASS,
                f'{employee.user.get_full_name()} is recorded as {status}.',
                source='StaffProfile.employment_status')
        return RuleResult(
            'permanent', "The employee's appointment", FAIL,
            f'{employee.user.get_full_name()} is recorded as {status}. '
            'Qualification (b) reaches the dependents of faculty and staff with '
            'a permanent appointment.',
            source='StaffProfile.employment_status')

    return RuleResult(
        'permanent', 'Permanent appointment', NEEDS_VERIFICATION,
        'Cannot be read until the application says whether the applicant is '
        'the employee or their dependent.',
        source='employment_status')


def _legitimate_dependent_rule(application: 'ApplicantRecord',
                               standing: str) -> RuleResult:
    """Whether a dependent has stated the relationship in full.

    Not applicable to an employee applying for themselves. For a dependent,
    both the relationship and the employee's name are required: half a
    declaration does not establish dependency, but it is missing information
    rather than a refusal.
    """
    if standing == STAFF:
        return RuleResult(
            'dependency', 'Legitimate dependent', PASS,
            'Not applicable — the applicant is the employee.',
            source='is_nsu_staff')
    if standing != DEPENDENT:
        return RuleResult(
            'dependency', 'Legitimate dependent', NEEDS_VERIFICATION,
            'Cannot be read until the application says whether the applicant is '
            'the employee or their dependent.',
            source='relationship_to_staff')

    relationship = (application.relationship_to_staff or '').strip()
    named = (application.staff_name or '').strip()
    missing = []
    if not relationship:
        missing.append('Relationship to the faculty or staff member')
    if not named:
        missing.append('Name of the faculty or staff member')
    if missing:
        return RuleResult(
            'dependency', 'Legitimate dependent', NEEDS_VERIFICATION,
            'The dependency has not been stated in full, so it has not been '
            'established. ' + ' '.join(m + ' is missing.' for m in missing),
            source='relationship_to_staff / staff_name',
            missing=tuple(missing))
    return RuleResult(
        'dependency', 'Legitimate dependent', PASS,
        f'Declared as the {relationship.lower()} of {named}.',
        source='relationship_to_staff')


def _no_baccalaureate_rule(application: 'ApplicantRecord',
                           standing: str) -> RuleResult:
    """Qualification (c): a dependent must not already hold a degree.

    Applies to dependents only. An employee who already has a baccalaureate is
    not disqualified — the programme exists partly so staff can study further.
    """
    if standing == STAFF:
        return RuleResult(
            'baccalaureate', 'No baccalaureate already', PASS,
            'Not applicable — qualification (c) disqualifies dependents who '
            'have already graduated, not employees.',
            source='is_nsu_staff')
    if standing != DEPENDENT:
        return RuleResult(
            'baccalaureate', 'No baccalaureate already', NEEDS_VERIFICATION,
            'Cannot be read until the application says whether the applicant is '
            'the employee or their dependent.',
            source='has_baccalaureate')
    if application.has_baccalaureate:
        return RuleResult(
            'baccalaureate', 'No baccalaureate already', FAIL,
            'Already holds a baccalaureate degree. Qualification (c) '
            'disqualifies staff dependents who have already graduated one.',
            source='has_baccalaureate')
    return RuleResult(
        'baccalaureate', 'No baccalaureate already', PASS,
        'No baccalaureate degree on record.', source='has_baccalaureate')


def evaluate(application: 'ApplicantRecord') -> Evaluation:
    """Judge one staff application against every qualification.

    A single failure refuses the application. Absent a failure, any rule that
    could not be run leaves the application for verification rather than
    approving it on incomplete information.

    Returns:
        An :class:`Evaluation` carrying every verdict and what is still needed.
    """
    standing, standing_rule = _standing_rule(application)
    rules = [
        standing_rule,
        _permanent_appointment_rule(application, standing),
        _legitimate_dependent_rule(application, standing),
        _no_baccalaureate_rule(application, standing),
    ]

    if any(r.failed for r in rules):
        status = NOT_QUALIFIED
    elif any(r.unverified for r in rules):
        status = FOR_VERIFICATION
    else:
        status = QUALIFIED

    missing: list[str] = []
    if status != NOT_QUALIFIED:
        for rule in rules:
            missing.extend(rule.missing)

    return Evaluation(
        application=application,
        standing=standing,
        rules=rules,
        status=status,
        missing=list(dict.fromkeys(missing)),
    )


def rank(applications: Iterable['ApplicantRecord']) -> list[Evaluation]:
    """Evaluate and order a set of staff applications.

    Unlike TES, nothing is screened out first: an incomplete application is
    ranked as "For Verification" so the office can see it and chase it, rather
    than disappearing from the list.

    Returns:
        Evaluations in recommendation order, each with ``rank`` filled in.
    """
    evaluations = [evaluate(a) for a in applications]
    evaluations.sort(key=lambda e: e.sort_key)
    for position, evaluation in enumerate(evaluations, start=1):
        evaluation.rank = position
    return evaluations
