"""The employee portal for the BiPSU Staff Scholarship.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render, redirect
from .models import STAFF_APPLICATION_DETAILS, ActivityLog, BIPSU_SCHOOLS, BIPSU_COURSES
import logging
from .views_shared import _active_term, _validate_proof, application_window_reason, renewal_window_reason

logger = logging.getLogger(__name__)


def _nsu_staff_required(view_fn):
    """Restrict a view to employee accounts."""
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        """Redirect anyone who is not an employee to sign in."""
        if not request.user.is_authenticated or request.user.role != 'nsu_staff':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper

def _staff_profile(user):
    """Get or create this account's staff profile."""
    from .models import StaffProfile
    profile, _ = StaffProfile.objects.get_or_create(user=user)
    return profile

def _as_date(value):
    """Coerce a stored or posted date to a ``date``.

    A detail field holds whatever was assigned to it until it has been read
    back from the database, so the same attribute is a ``date`` on a reloaded
    row and a string on a freshly saved one. Comparing the two forms without
    this silently answers "different" for the same day.
    """
    from datetime import date, datetime
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date) or value is None:
        return value
    try:
        return datetime.strptime(str(value).strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_date(raw):
    """Parse a posted date.

    Returns:
        ``(date, ok)``. A blank field is ``(None, True)`` — not filled in
        is not the same as filled in wrongly, and only one of them is an
        error worth showing.
    """
    from datetime import datetime
    raw = (raw or '').strip()
    if not raw:
        return None, True
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date(), True
    except ValueError:
        return None, False

def _pick(application, staff, field):
    """The posted value for a field, or what is already stored."""
    value = getattr(application, field, '') if application else ''
    return value or getattr(staff, field, '') or ''

def _pick_date(application, staff, field):
    """The posted date for a field, or what is already stored."""
    value = getattr(application, field, None) if application else None
    value = value or getattr(staff, field, None)
    return value.strftime('%Y-%m-%d') if value else ''

def _staff_application_for(user, term=None):
    """Return this employee's own Staff-scholarship record for one term.

    The lookup is narrowed three ways, and each one rules out a distinct false
    positive that would otherwise refuse a legitimate application:

    ``qualified_for='Staff'``
        Their staff award, not some other programme they happen to hold.
    dependents excluded
        A dependent's record is filed under ``qualified_for='Staff'`` as well,
        but it belongs to an employee's child. It must never stand in for the
        employee's own application.
    the active term
        Every write path stamps the record with the term it was filed in, so a
        lookup that ignores the term keeps returning last semester's record and
        locks the employee out of the programme permanently.

    Rejected records are skipped so that a refusal does not bar a resubmission.

    Args:
        user: the signed-in staff account.
        term: a parsed term mapping as returned by :func:`_active_term`. Read
            from ``SystemSettings`` when omitted.

    Returns:
        The matching ``ApplicantRecord``, or ``None`` when they have not
        applied this term.
    """
    from .models import ApplicantRecord
    if term is None:
        term = _active_term()
    return (ApplicantRecord.objects
            .filter(email=user.email, qualified_for='Staff',
                    school_year=term['sy'], semester=term['semester'])
            .exclude(status='Rejected')
            .exclude(staff_eligibility__is_nsu_dependent=True)
            .order_by('-submitted_at')
            .first())

def _nsu_staff_enrolled(user):
    """Whether this employee already holds a staff award for the active term.

    Drives the sidebar: the "Apply" link is hidden while a record exists. It is
    deliberately term-scoped so the link returns each new term, matching the
    guard in :func:`nsu_staff_apply`.
    """
    return _staff_application_for(user) is not None

@_nsu_staff_required
def nsu_staff_dashboard(request):
    """The employee portal's landing page."""
    from .models import StaffRenewal, Notification, Announcement
    user = request.user
    aff_app = _staff_application_for(user)
    renewals = StaffRenewal.objects.filter(staff_user=user).order_by('-submitted_at')
    announcements = Announcement.objects.order_by('-created_at')[:3]
    unread_count = Notification.objects.filter(
        student__user=user, is_read=False
    ).count() if hasattr(user, 'profile') else 0
    return render(request, 'nsu_staff/dashboard.html', {
        'aff_app': aff_app,
        'renewals': renewals,
        'announcements': announcements,
        'unread_count': unread_count,
        'pending_renewals': renewals.filter(status='Pending').count(),
        'approved_renewals': renewals.filter(status='Approved').count(),
        'enrolled': _nsu_staff_enrolled(user),
    })

@_nsu_staff_required
def nsu_staff_profile(request):
    """View and update an employee's own profile."""
    from .models import ApplicantRecord, StaffProfile
    from .constants import (BIPSU_STAFF_UNIT_GROUPS, CIVIL_STATUSES,
                            DESIGNATIONS, EMPLOYMENT_STATUSES)
    user = request.user
    staff = _staff_profile(user)
    aff_app = ApplicantRecord.objects.filter(
        email=user.email, qualified_for='Staff'
    ).exclude(
        staff_eligibility__is_nsu_dependent=True
    ).order_by('-submitted_at').first()
    saved = False
    errors = []
    if request.method == 'POST':
        p = request.POST
        user.first_name = p.get('first_name', user.first_name).strip()
        user.last_name  = p.get('last_name',  user.last_name).strip()
        user.save()

        staff.middle_name    = p.get('middle_name', staff.middle_name).strip()
        staff.suffix         = p.get('suffix', staff.suffix).strip()
        staff.gender         = p.get('gender', staff.gender)
        staff.civil_status   = p.get('civil_status', staff.civil_status)
        staff.contact_number = p.get('contact_number', staff.contact_number).strip()
        staff.barangay       = p.get('barangay', staff.barangay)
        staff.municipality   = p.get('municipality', staff.municipality)
        staff.province       = p.get('province', staff.province)

        employee_id = p.get('employee_id', staff.employee_id).strip()
        clash = StaffProfile.objects.filter(employee_id=employee_id).exclude(pk=staff.pk)
        if employee_id and clash.exists():
            errors.append(f'Employee ID {employee_id} is already on another staff record. '
                          'Contact the VPSEA office if that is not right.')
        else:
            staff.employee_id = employee_id
        staff.school            = p.get('school', staff.school)
        staff.department        = p.get('department', staff.department).strip()
        staff.position          = p.get('position', staff.position).strip()
        staff.employment_status = p.get('employment_status', staff.employment_status)
        staff.designation       = p.get('designation', staff.designation)
        staff.highest_education = p.get('highest_education', staff.highest_education).strip()
        staff.has_baccalaureate = 'has_baccalaureate' in p

        for field, label in (
            ('date_of_birth', 'Date of birth'),
            ('date_hired', 'Date hired'),
            ('date_of_regularization', 'Date of regularization'),
        ):
            parsed, ok = _parse_date(p.get(field, ''))
            if ok:
                setattr(staff, field, parsed)
            else:
                errors.append(f'{label} must be a valid date.')

        yos = p.get('years_of_service', '').strip()
        if yos == '':
            staff.declared_years_of_service = None
        elif yos.isdigit():
            staff.declared_years_of_service = int(yos)
        else:
            errors.append('Years of service must be a whole number of years.')

        if request.FILES.get('appointment_paper'):
            staff.appointment_paper = request.FILES['appointment_paper']
        if request.FILES.get('photo'):
            user.photo = request.FILES['photo']
            user.save(update_fields=['photo'])

        staff.save()
        saved = not errors
        if saved:
            ActivityLog.record(
                user, 'Updated their own staff profile',
                verb='update', target=staff, request=request)
    return render(request, 'nsu_staff/profile.html', {
        'staff': staff,
        'aff_app': aff_app,
        'saved': saved,
        'errors': errors,
        'bipsu_staff_units': BIPSU_STAFF_UNIT_GROUPS,
        'civil_statuses': CIVIL_STATUSES,
        'employment_statuses': EMPLOYMENT_STATUSES,
        'designations': DESIGNATIONS,
        'enrolled': _nsu_staff_enrolled(user),
    })

@_nsu_staff_required
def nsu_staff_notifications(request):
    """Notifications for an employee."""
    from .models import Notification
    user = request.user
    notifications = []
    if hasattr(user, 'profile'):
        notifications = Notification.objects.filter(
            student=user.profile
        ).order_by('-created_at')
        if request.method == 'POST' and request.POST.get('mark_all_read'):
            notifications.update(is_read=True)
            return redirect('/nsu-staff/notifications/')
    return render(request, 'nsu_staff/notifications.html', {
        'notifications': notifications,
        'enrolled': _nsu_staff_enrolled(user),
    })

@_nsu_staff_required
def nsu_staff_applications(request):
    """An employee's own applications and renewals, and their dependents'.

    A dependent's record is filed under the dependent's email, so it is found
    by the employee number it was filed against rather than by address.
    """
    from django.db.models import Q
    from .models import ApplicantRecord, StaffRenewal
    user = request.user
    mine = (ApplicantRecord.objects.filter(email=user.email)
            .exclude(staff_eligibility__is_nsu_dependent=True))
    applications = (ApplicantRecord.objects
                    .filter(Q(pk__in=mine.values('pk'))
                            | Q(pk__in=_dependent_records_for(user)
                                .values('pk')))
                    .select_related('linked_student__user',
                                    *STAFF_APPLICATION_DETAILS)
                    .order_by('-submitted_at'))
    renewals = StaffRenewal.objects.filter(staff_user=user).order_by('-submitted_at')
    return render(request, 'nsu_staff/applications.html', {
        'applications': applications,
        'renewals': renewals,
        'enrolled': _nsu_staff_enrolled(user),
    })

@_nsu_staff_required
def nsu_staff_renewal(request):
    """File a renewal for an existing staff award.

    Scoped and guarded the way the student renewal is. It was neither: the
    list showed every renewal the employee had ever filed, and a POST created
    a new row unconditionally, so each resubmission added another — which is
    why the page filled up with history nobody asked for. Nothing checked the
    renewal window either, so one could be filed while renewals were closed.
    """
    from .models import StaffRenewal, SystemSettings
    user = request.user
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    label = settings_obj.academic_year

    renewals = (StaffRenewal.objects
                .filter(staff_user=user, term_label=label)
                .order_by('-submitted_at'))
    shut = renewal_window_reason('Staff')

    def page(**extra):
        """Render the renewal page with the current context."""
        context = {
            'renewals': renewals,
            'submitted': request.GET.get('submitted'),
            'semester': parsed['semester'],
            'academic_year': parsed['sy'],
            'errors': [],
            'blocked': bool(shut),
            'blocked_reason': shut,
            'enrolled': _nsu_staff_enrolled(user),
        }
        context.update(extra)
        return render(request, 'nsu_staff/renewal.html', context)

    if shut:
        return page()

    if request.method == 'POST':
        document = request.FILES.get('supporting_document')
        if not document:
            return page(errors=['A supporting document is required.'])

        problems = _validate_proof(document, settings_obj)
        if problems:
            return page(errors=problems)

        pending = renewals.filter(status='Pending').first()
        if pending:
            pending.supporting_document = document
            pending.save(update_fields=['supporting_document'])
        else:
            renewal = StaffRenewal.objects.create(
                staff_user=user, supporting_document=document)
            ActivityLog.record(
                user, f'Submitted a Staff Scholarship renewal for '
                      f'{renewal.term_label}',
                verb='create', target=renewal, request=request)
        return redirect('/nsu-staff/renewal/?submitted=1')

    return page()

SELF_KIND = 'self'
DEPENDENT_KIND = 'dependent'


def _applicant_kind(data):
    """Whether a form is the employee's own application or a dependent's.

    Anything but an explicit dependent choice reads as the employee's own, so
    a form posted without the field keeps the behaviour it had before
    dependents could be filed here.
    """
    return (DEPENDENT_KIND if data.get('applicant_kind') == DEPENDENT_KIND
            else SELF_KIND)


def _match_dependent_student(student_number, date_of_birth):
    """Find the portal account a dependent's details point at.

    The student number is the key, because it is unique across profiles. It is
    confirmed against the date of birth rather than the surname: a dependent
    may be a spouse or a legal ward who shares no name with the employee, and
    plenty of unrelated students share one.

    A profile with no recorded date of birth is matched on the number alone.
    There is nothing to check it against, and refusing the link would punish
    the student for a field nobody filled in.

    Args:
        student_number: the dependent's student number as posted.
        date_of_birth: their date of birth as posted, ``YYYY-MM-DD``.

    Returns:
        ``(profile, problem)``. Both are empty when no account carries that
        number, which is not an error: a dependent who has not registered yet
        may still be applied for. ``problem`` is a sentence for the employee
        when the number belongs to somebody born on another date.
    """
    from .models import StudentProfile

    number = (student_number or '').strip()
    if not number:
        return None, ''

    profile = (StudentProfile.objects.select_related('user')
               .filter(student_id=number).first())
    if profile is None:
        return None, ''

    posted, ok = _parse_date(date_of_birth)
    recorded = _as_date(profile.date_of_birth)
    if recorded and ok and posted and recorded != posted:
        return None, (
            f'Student number {number} belongs to an account with a different '
            'date of birth. Check the number on your dependent\'s '
            'registration: filing under it would attach this award to '
            'somebody else.')
    return profile, ''


def _dependent_records_for(user):
    """Every dependent application this employee has filed.

    Matched on the employee number they filed under rather than on the email,
    because a dependent's record carries the dependent's address, not theirs.
    """
    from .models import ApplicantRecord

    staff = _staff_profile(user)
    if not staff.employee_id:
        return ApplicantRecord.objects.none()
    return (ApplicantRecord.objects
            .filter(qualified_for='Staff',
                    staff_eligibility__is_nsu_dependent=True,
                    staff_eligibility__staff_employee_id=staff.employee_id)
            .select_related('linked_student__user', *STAFF_APPLICATION_DETAILS)
            .order_by('-submitted_at'))


def _dependent_already_claimed(profile, student_number, term, existing):
    """Why this dependent cannot be applied for again, if they cannot.

    Two doors lead to the same award: the employee filing here, and the
    dependent declaring it themselves at registration. Whichever came first
    stands, because the office should not be asked to decide one award twice.
    """
    from .models import (ApplicantRecord, ScholarshipLinkRequest,
                         SystemSettings)

    if profile is not None:
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        declared = (ScholarshipLinkRequest.objects
                    .filter(student=profile, scholarship_type='Staff',
                            term_label=settings_obj.academic_year)
                    .exclude(status='Rejected')
                    .order_by('submitted_at').first())
        if declared is not None:
            return (f'{profile.user.get_full_name()} already declared the '
                    'BiPSU Staff Scholarship on their own account and the '
                    f'SDSO has it as {declared.status.lower()}. Wait for that '
                    'decision rather than filing the same award beside it.')

    filed = (ApplicantRecord.objects
             .filter(qualified_for='Staff',
                     school_year=term['sy'], semester=term['semester'],
                     enrollment__student_id=(student_number or '').strip(),
                     staff_eligibility__is_nsu_dependent=True)
             .exclude(status='Rejected'))
    if existing is not None:
        filed = filed.exclude(pk=existing.pk)
    first = filed.order_by('submitted_at').first()
    if first is not None:
        return (f'Student number {student_number} already has a Staff '
                f'Scholarship application this term ({first.status}). One '
                'stands per dependent per term.')
    return ''


def _dependent_apply_errors(posted, files, existing):
    """Everything wrong with an application filed for a dependent."""
    from .constants import RELATIONSHIP_TO_STAFF_CHOICES

    errors = [f'{label} is required.'
              for field, label in DEPENDENT_APPLY_REQUIRED.items()
              if not posted.get(field, '').strip()]

    relationship = posted.get('relationship_to_staff', '').strip()
    if not relationship:
        errors.append('Your relationship to the dependent is required.')
    elif relationship not in [r for r, _ in RELATIONSHIP_TO_STAFF_CHOICES]:
        errors.append('Say how your dependent is related to you: son, '
                      'daughter, spouse or legal ward.')

    employment = posted.get('employment_status', '').strip()
    if employment and employment != 'Regular':
        errors.append(
            'The BiPSU Staff Scholarship rests on a regular appointment. '
            f'Yours is recorded as {employment} - contact the VPSEA office '
            'if that is out of date.')
    if not files.get('appointment_paper') and not (
            existing and existing.appointment_paper):
        errors.append('Appointment paper document is required. The award '
                      'rests on your appointment, not your dependent\'s.')

    profile, mismatch = _match_dependent_student(
        posted.get('student_number', ''), posted.get('date_of_birth', ''))
    if mismatch:
        errors.append(mismatch)
    else:
        claimed = _dependent_already_claimed(
            profile, posted.get('student_number', ''), _active_term(), existing)
        if claimed:
            errors.append(claimed)
    return errors


STAFF_APPLY_REQUIRED = {
    'first_name': 'First name',
    'last_name': 'Last name',
    'date_of_birth': 'Date of birth',
    'gender': 'Gender',
    'course': 'Course',
    'student_number': 'Student / Employee number',
    'employment_status': 'Employment status',
    'designation': 'Designation',
    'years_of_service': 'Years of service',
    'date_of_regularization': 'Date of regularization',
}

DEPENDENT_APPLY_REQUIRED = {
    'first_name': "Dependent's first name",
    'last_name': "Dependent's last name",
    'date_of_birth': "Dependent's date of birth",
    'gender': "Dependent's gender",
    'course': "Dependent's course",
    'student_number': "Dependent's student number",
    'employee_number': 'Your employee number',
    'employment_status': 'Employment status',
    'designation': 'Designation',
    'years_of_service': 'Years of service',
    'date_of_regularization': 'Date of regularization',
}


def _staff_apply_errors(posted, files, existing):
    """Everything wrong with a submitted staff application."""
    if _applicant_kind(posted) == DEPENDENT_KIND:
        return _dependent_apply_errors(posted, files, existing)

    errors = [f'{label} is required.'
              for field, label in STAFF_APPLY_REQUIRED.items()
              if not posted.get(field, '').strip()]

    employment = posted.get('employment_status', '').strip()
    if employment and employment != 'Regular':
        errors.append(
            'The BiPSU Staff Scholarship is open to regular employees. '
            f'Your appointment is recorded as {employment} — contact the '
            'VPSEA office if that is out of date.'
        )
    if not files.get('appointment_paper') and not (
            existing and existing.appointment_paper):
        errors.append('Appointment paper document is required.')
    return errors


def _years_of_service(posted):
    """The years of service posted, or 0 where it will not convert."""
    try:
        return int(posted.get('years_of_service', 0) or 0)
    except (ValueError, TypeError):
        return 0


def _resubmit_staff_record(record, posted, files, full_name, years):
    """Update an application the staff member is submitting again.

    Only answered fields overwrite, because a resubmission after a rejection
    carries the corrected answers and not necessarily the whole form again.
    """
    record.full_name = full_name or record.full_name
    record.contact_number = posted.get('contact_number', record.contact_number)
    record.barangay = posted.get('barangay', record.barangay)
    record.municipality = posted.get('municipality', record.municipality)
    record.province = posted.get('province', record.province)
    if posted.get('date_of_birth'):
        record.date_of_birth = posted.get('date_of_birth')
    if posted.get('gender'):
        record.gender = posted.get('gender')
    if posted.get('course'):
        record.course = posted.get('course')
    if posted.get('student_number'):
        record.student_id = posted.get('student_number')
    record.employment_status = posted.get(
        'employment_status', record.employment_status)
    record.designation = posted.get('designation', record.designation)
    if years:
        record.years_of_service = years
    if posted.get('date_of_regularization'):
        record.date_of_regularization = posted.get('date_of_regularization')
    record.is_nsu_staff = True
    record.is_nsu_dependent = False
    record.status = 'Pending Validation'
    record.remarks = ''
    if files.get('appointment_paper'):
        record.appointment_paper = files.get('appointment_paper')
    record.save()
    return record


def _new_staff_record(user, posted, files, full_name, years, kind=SELF_KIND,
                      profile=None):
    """File a staff application for the first time.

    Args:
        kind: :data:`SELF_KIND` for the employee's own, :data:`DEPENDENT_KIND`
            for one filed on a dependent's behalf.
        profile: the dependent's portal account where they have one.

    A dependent's record is filed under the dependent's own email, never the
    employee's. Under the employee's it would be picked up as their own
    application everywhere the portal looks one up by address, and the
    decision would be mailed to the wrong person.
    """
    from .models import ApplicantRecord

    try:
        year_level = int(posted.get('year_level', 1) or 1)
    except (ValueError, TypeError):
        year_level = 1

    if kind == DEPENDENT_KIND:
        email = (profile.user.email if profile is not None
                 else posted.get('dependent_email', '').strip())
    else:
        email = user.email

    return ApplicantRecord.objects.create(
        full_name=full_name,
        email=email,
        contact_number=posted.get('contact_number', ''),
        barangay=posted.get('barangay', ''),
        municipality=posted.get('municipality', ''),
        province=posted.get('province', ''),
        date_of_birth=posted.get('date_of_birth') or None,
        gender=posted.get('gender', ''),
        course=posted.get('course', ''),
        year_level=year_level,
        student_id=posted.get('student_number', ''),
        is_nsu_staff=(kind == SELF_KIND),
        employment_status=posted.get('employment_status', ''),
        designation=posted.get('designation', ''),
        years_of_service=years or None,
        date_of_regularization=posted.get('date_of_regularization') or None,
        appointment_paper=files.get('appointment_paper') or None,
        qualified_for='Staff',
        status='Pending Validation',
    )


def _attach_dependent(record, user, posted, profile):
    """Stamp a dependent's record with the employee the award rests on.

    The link to the student's account is what makes the award theirs on their
    own portal. Where they have no account the record still stands, unlinked,
    the way an imported scholar does.
    """
    record.is_nsu_staff = False
    record.is_nsu_dependent = True
    record.staff_name = user.get_full_name()
    record.staff_employee_id = posted.get('employee_number', '').strip()
    record.relationship_to_staff = posted.get('relationship_to_staff', '').strip()
    record.linked_student = profile
    record.save()
    return record


def _sync_staff_profile(staff, record, posted, years, kind=SELF_KIND):
    """Carry the application's answers back onto the employee's profile.

    Only the employment half of a dependent's application is the employee's.
    The name, address, birthday and student number on it are the dependent's,
    and copying those onto the profile would overwrite the employee with their
    own child.
    """
    if kind == SELF_KIND:
        staff.employee_id = posted.get('student_number', '').strip() or staff.employee_id
        staff.contact_number = posted.get('contact_number', '').strip() or staff.contact_number
        staff.gender = posted.get('gender', '') or staff.gender
        staff.barangay = posted.get('barangay', '') or staff.barangay
        staff.municipality = posted.get('municipality', '') or staff.municipality
        staff.province = posted.get('province', '') or staff.province
        born, ok = _parse_date(posted.get('date_of_birth', ''))
        if ok and born:
            staff.date_of_birth = born
    else:
        staff.employee_id = posted.get('employee_number', '').strip() or staff.employee_id

    staff.employment_status = posted.get('employment_status', '') or staff.employment_status
    staff.designation = posted.get('designation', '') or staff.designation
    if years:
        staff.declared_years_of_service = years

    regularized, ok = _parse_date(posted.get('date_of_regularization', ''))
    if ok and regularized:
        staff.date_of_regularization = regularized
    if record.appointment_paper:
        staff.appointment_paper = record.appointment_paper.name
    staff.save()


def _dependent_apply_prefill(staff):
    """What the dependent form opens with.

    Nothing of the employee's own but their employment, because every other
    field on the form describes the dependent.
    """
    return {
        'first_name': '', 'last_name': '', 'date_of_birth': '', 'gender': '',
        'contact_number': '', 'barangay': '', 'municipality': '',
        'province': '', 'student_number': '', 'year_level': 1, 'course': '',
        'dependent_email': '', 'relationship_to_staff': '',
        'employee_number': staff.employee_id,
        'employment_status': staff.employment_status or '',
        'designation': staff.designation or '',
        'years_of_service': (staff.years_of_service
                             if staff.years_of_service is not None else ''),
        'date_of_regularization': _pick_date(None, staff,
                                             'date_of_regularization'),
    }


def _staff_apply_prefill(existing, staff, user, kind=SELF_KIND):
    """What the form opens with, preferring the application over the profile."""
    if kind == DEPENDENT_KIND:
        return _dependent_apply_prefill(staff)
    parts = (existing.full_name or '').split() if existing else []
    return {
        'first_name': parts[0] if parts else user.first_name,
        'last_name': parts[-1] if len(parts) > 1 else user.last_name,
        'date_of_birth': _pick_date(existing, staff, 'date_of_birth'),
        'gender': _pick(existing, staff, 'gender'),
        'contact_number': _pick(existing, staff, 'contact_number'),
        'barangay': _pick(existing, staff, 'barangay'),
        'municipality': _pick(existing, staff, 'municipality'),
        'province': _pick(existing, staff, 'province'),
        'student_number': (existing.student_id if existing and existing.student_id
                           else staff.employee_id),
        'year_level': existing.year_level if existing else 1,
        'course': existing.course if existing else '',
        'employment_status': _pick(existing, staff, 'employment_status'),
        'designation': _pick(existing, staff, 'designation'),
        'years_of_service': (
            existing.years_of_service
            if existing and existing.years_of_service is not None
            else staff.years_of_service if staff.years_of_service is not None
            else ''),
        'date_of_regularization': _pick_date(
            existing, staff, 'date_of_regularization'),
    }


def _save_staff_application(request, staff, existing):
    """Record a valid staff application, new or resubmitted."""
    posted, files = request.POST, request.FILES
    kind = _applicant_kind(posted)
    full_name = (f"{posted.get('first_name', '').strip()} "
                 f"{posted.get('last_name', '').strip()}").strip()
    years = _years_of_service(posted)

    if kind == DEPENDENT_KIND:
        profile, _ = _match_dependent_student(
            posted.get('student_number', ''), posted.get('date_of_birth', ''))
        record = _new_staff_record(request.user, posted, files, full_name,
                                   years, kind, profile)
        _attach_dependent(record, request.user, posted, profile)
    elif existing:
        record = _resubmit_staff_record(existing, posted, files, full_name, years)
    else:
        record = _new_staff_record(request.user, posted, files, full_name, years)
    _sync_staff_profile(staff, record, posted, years, kind)
    return record


def _dependent_filed_log(record):
    """What the activity log says about an application filed for a dependent."""
    who = f'{record.full_name} ({record.student_id})'
    tie = (record.relationship_to_staff or 'dependent').lower()
    where = ('linked to their portal account' if record.linked_student_id
             else 'no portal account matched')
    return (f'Applied for the BiPSU Staff Scholarship on behalf of {who}, '
            f'their {tie} - {where} ({record.term_label})')


@_nsu_staff_required
def nsu_staff_apply(request):
    """Apply for the BiPSU Staff Scholarship, for oneself or a dependent.

    The two are one form because they are one programme and one appointment
    backs both. Which of them is being filed is read from ``applicant_kind``,
    and an employee who already holds their own application may still file for
    a dependent - their own record is not what bars it.
    """
    from .constants import EMPLOYMENT_STATUSES, RELATIONSHIP_TO_STAFF_CHOICES

    user = request.user
    staff = _staff_profile(user)
    kind = _applicant_kind(
        request.POST if request.method == 'POST' else request.GET)
    existing = _staff_application_for(user) if kind == SELF_KIND else None

    if existing and existing.status in ('Approved', 'Pending Validation'):
        return render(request, 'nsu_staff/apply.html', {
            'blocked': True,
            'blocked_reason': ('You already have a Staff Scholarship '
                               f'application with status: {existing.status}.'),
            'existing': existing,
            'enrolled': True,
            'dependent_offer': True,
        })

    shut = application_window_reason('Staff')
    if shut:
        return render(request, 'nsu_staff/apply.html', {
            'blocked': True, 'blocked_reason': shut,
            'existing': existing, 'enrolled': bool(existing),
        })

    errors = []
    if request.method == 'POST':
        errors = _staff_apply_errors(request.POST, request.FILES, existing)
        if not errors:
            record = _save_staff_application(request, staff, existing)
            if kind == DEPENDENT_KIND:
                ActivityLog.record(
                    user, _dependent_filed_log(record), verb='create',
                    target=record, request=request)
                landed = 'linked' if record.linked_student_id else 'unlinked'
                return redirect('/nsu-staff/apply/?applicant_kind=dependent'
                                f'&submitted={landed}')
            ActivityLog.record(
                user,
                f'{"Resubmitted" if existing else "Applied"} for the BiPSU '
                f'Staff Scholarship ({record.term_label})',
                verb='update' if existing else 'create',
                target=record, request=request)
            return redirect('/nsu-staff/apply/?submitted=1')

    return render(request, 'nsu_staff/apply.html', {
        'blocked': False,
        'existing': existing,
        'submitted': request.GET.get('submitted'),
        'errors': errors,
        'user': user,
        'applicant_kind': kind,
        'for_dependent': kind == DEPENDENT_KIND,
        'relationships': RELATIONSHIP_TO_STAFF_CHOICES,
        'bipsu_courses': BIPSU_COURSES,
        'bipsu_schools': BIPSU_SCHOOLS,
        'employment_statuses': EMPLOYMENT_STATUSES,
        'enrolled': _nsu_staff_enrolled(user),
        'prefill': _staff_apply_prefill(existing, staff, user, kind),
    })
