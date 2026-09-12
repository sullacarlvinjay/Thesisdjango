"""Rule-based recommender for the BiPSU Faculty and Staff Scholars programme.

    This kind of scholarship grant is a specialized program of the University
    that gives full privilege to the members of the faculty and staff and their
    legitimate dependents as approved by the Board of Regents, with the
    following qualifications:

      a. All faculty and employees of the University with permanent appointment.
      b. All qualified and legitimate dependents of faculty and staff with
         permanent appointment.
      c. Staff dependents who have already graduated a baccalaureate degree are
         disqualified from enjoying the scholarship.

Three qualifications, and this module is the whole of them. There is no merit
test to rank on — nobody is scored, nothing is weighted — so what it produces is
a *verdict with a reason*, not a league table. Rows are ordered by how settled
the answer is and then by name, which is the order the office reads a list in.

Like :mod:`api.tes_ranking`, nothing here writes to the database. It reads the
application the office already holds and states what the rules make of it, so
re-running it can never change a record and the answer can never go stale.

The distinction it is built around is the same one: **failing** a rule and **not
knowing** whether it was met are different answers.

  * A dependent whose parent's employee ID matches no staff record has not
    failed qualification (b) — nobody has been able to check it. The office is
    told the ID it could not find, so it can go and find it.
  * A row that says neither staff nor dependent has not failed either; it was
    never asked. Two of the three qualifications turn on which of the two the
    applicant is, so that question is a rule in its own right.

Rule (c) applies to dependents and only to dependents. An employee with a degree
already is qualified under (a) — the programme is a condition of their
employment, not a first-degree grant — and reading (c) onto them would turn away
most of the faculty.

Field mapping (qualification -> the field actually read). Every one of them is
on the application, which is where the applicant answered it:

    Staff or dependent      AffirmativeStaffApplication.is_nsu_staff
                            AffirmativeStaffApplication.is_nsu_dependent
    (a) Permanent           AffirmativeStaffApplication.employment_status
    (b) The employee behind AffirmativeStaffApplication.staff_employee_id
        a dependent         AffirmativeStaffApplication.staff_name
                            StaffProfile.employment_status  (looked up by ID)
    (b) Legitimate          AffirmativeStaffApplication.relationship_to_staff
    (c) Already a graduate  AffirmativeStaffApplication.has_baccalaureate
"""
from dataclasses import dataclass, field

PASS = 'PASS'
FAIL = 'FAIL'
NEEDS_VERIFICATION = 'NEEDS VERIFICATION'

QUALIFIED = 'Qualified'
NOT_QUALIFIED = 'Not Qualified'
FOR_VERIFICATION = 'For Verification'

STAFF = 'Employee'
DEPENDENT = 'Dependent'
UNSTATED = 'Not stated'

# The one appointment that qualifies. 'Permanent' is what the Board's wording
# calls it and 'Regular' is what EMPLOYMENT_STATUSES stores, so both are
# accepted rather than making the office learn which word this screen wants.
PERMANENT_APPOINTMENTS = ('Regular', 'Permanent')


@dataclass(frozen=True)
class RuleResult:
    """One qualification, the verdict on it, and why."""
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
    """Everything the office needs to see, and to defend, for one applicant."""
    application: object
    standing: str
    rules: list
    status: str
    missing: list = field(default_factory=list)
    rank: int = None

    @property
    def applicant_name(self):
        return self.application.full_name

    @property
    def qualified(self):
        return self.status == QUALIFIED

    @property
    def needs_verification(self):
        return self.status == FOR_VERIFICATION

    @property
    def recommendation(self):
        """The one-line verdict shown in the Recommendation column."""
        if self.status == NOT_QUALIFIED:
            return 'Not Recommended'
        if self.status == FOR_VERIFICATION:
            return 'For Verification'
        return 'Recommended'

    def rule(self, key):
        for r in self.rules:
            if r.key == key:
                return r
        return None

    # The two verdicts that get a column of their own on the ranking table.
    # Named properties rather than a lookup in the template: Django's template
    # language cannot call rule('permanent'), and a filter written to do it
    # would be a filter that exists for one table.
    @property
    def permanent_verdict(self):
        return self.rule('permanent').verdict

    @property
    def baccalaureate_verdict(self):
        return self.rule('baccalaureate').verdict

    @property
    def sort_key(self):
        """Settled answers first, then the ones still to be checked, then name.

        Nothing is scored, so there is nothing to rank on beyond how finished
        the answer is. Sorting the qualified to the top is the office's own
        reading order — those are the rows it acts on.
        """
        status_rank = {QUALIFIED: 0, FOR_VERIFICATION: 1, NOT_QUALIFIED: 2}[self.status]
        return (status_rank, (self.application.full_name or '').lower())


# ── the individual qualifications ───────────────────────────────────────────

def _standing_rule(application):
    """Which of the two the applicant is. Neither qualification (a) nor (b)
    can be read until this one is answered, so it is asked first."""
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


def _permanent_appointment_rule(application, standing):
    """Qualification (a) for an employee, and the first half of (b) for a
    dependent — in both cases: is the appointment behind this a permanent one?"""
    if standing == STAFF:
        status = (application.employment_status or '').strip()
        if not status:
            return RuleResult(
                'permanent', 'Permanent appointment', NEEDS_VERIFICATION,
                'No appointment status is recorded on the application, so '
                'whether it is permanent cannot be read.',
                source='employment_status',
                missing=('Employment status on the application',))
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
        # Imported by name so the module stays importable without Django
        # configured, the way api.tes_ranking is.
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


def _legitimate_dependent_rule(application, standing):
    """The other half of qualification (b): a *legitimate* dependent, which is
    the relationship the applicant declared to the employee.

    An employee applying for themselves passes it trivially — there is no
    dependency to establish — and saying so is clearer on screen than leaving
    the row blank.
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


def _no_baccalaureate_rule(application, standing):
    """Qualification (c), and it disqualifies rather than qualifies.

    Dependents only. An employee who already holds a degree is qualified under
    (a) — the programme is part of their employment, not a first-degree grant —
    so reading (c) onto them would turn away most of the faculty.
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


# ── putting them together ───────────────────────────────────────────────────

def evaluate(application):
    """Run all four rules over one application and reach a verdict."""
    standing, standing_rule = _standing_rule(application)
    rules = [
        standing_rule,
        _permanent_appointment_rule(application, standing),
        _legitimate_dependent_rule(application, standing),
        _no_baccalaureate_rule(application, standing),
    ]

    # A failure settles it even when something else is unchecked: a dependent
    # who has already graduated is disqualified whether or not their parent's
    # ID was found, and sending the office to look it up would waste the trip.
    if any(r.failed for r in rules):
        status = NOT_QUALIFIED
    elif any(r.unverified for r in rules):
        status = FOR_VERIFICATION
    else:
        status = QUALIFIED

    missing = []
    if status != NOT_QUALIFIED:
        for rule in rules:
            missing.extend(rule.missing)

    return Evaluation(
        application=application,
        standing=standing,
        rules=rules,
        status=status,
        missing=list(dict.fromkeys(missing)),   # de-duplicated, order kept
    )


def rank(applications):
    """Evaluate a set of applications and number them from 1.

    Everyone appears, including applications too incomplete to decide — they
    are marked For Verification rather than dropped, so the office can see who
    still needs chasing instead of quietly losing them.
    """
    evaluations = [evaluate(a) for a in applications]
    evaluations.sort(key=lambda e: e.sort_key)
    for position, evaluation in enumerate(evaluations, start=1):
        evaluation.rank = position
    return evaluations
