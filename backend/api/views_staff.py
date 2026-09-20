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
    """An employee's own applications and renewals."""
    from .models import ApplicantRecord, StaffRenewal
    user = request.user
    applications = ApplicantRecord.objects.filter(
        email=user.email
    ).select_related(*STAFF_APPLICATION_DETAILS).order_by('-submitted_at')
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


def _staff_apply_errors(posted, files, existing):
    """Everything wrong with a submitted staff application."""
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
    record.status = 'Pending Validation'
    record.remarks = ''
    if files.get('appointment_paper'):
        record.appointment_paper = files.get('appointment_paper')
    record.save()
    return record


def _new_staff_record(user, posted, files, full_name, years):
    """File a staff application for the first time."""
    from .models import ApplicantRecord

    try:
        year_level = int(posted.get('year_level', 1) or 1)
    except (ValueError, TypeError):
        year_level = 1

    return ApplicantRecord.objects.create(
        full_name=full_name,
        email=user.email,
        contact_number=posted.get('contact_number', ''),
        barangay=posted.get('barangay', ''),
        municipality=posted.get('municipality', ''),
        province=posted.get('province', ''),
        date_of_birth=posted.get('date_of_birth') or None,
        gender=posted.get('gender', ''),
        course=posted.get('course', ''),
        year_level=year_level,
        student_id=posted.get('student_number', ''),
        is_nsu_staff=True,
        employment_status=posted.get('employment_status', ''),
        designation=posted.get('designation', ''),
        years_of_service=years or None,
        date_of_regularization=posted.get('date_of_regularization') or None,
        appointment_paper=files.get('appointment_paper') or None,
        qualified_for='Staff',
        status='Pending Validation',
    )


def _sync_staff_profile(staff, record, posted, years):
    """Carry the application's answers back onto the employee's profile."""
    staff.employee_id = posted.get('student_number', '').strip() or staff.employee_id
    staff.contact_number = posted.get('contact_number', '').strip() or staff.contact_number
    staff.gender = posted.get('gender', '') or staff.gender
    staff.barangay = posted.get('barangay', '') or staff.barangay
    staff.municipality = posted.get('municipality', '') or staff.municipality
    staff.province = posted.get('province', '') or staff.province
    staff.employment_status = posted.get('employment_status', '') or staff.employment_status
    staff.designation = posted.get('designation', '') or staff.designation
    if years:
        staff.declared_years_of_service = years

    born, ok = _parse_date(posted.get('date_of_birth', ''))
    if ok and born:
        staff.date_of_birth = born
    regularized, ok = _parse_date(posted.get('date_of_regularization', ''))
    if ok and regularized:
        staff.date_of_regularization = regularized
    if record.appointment_paper:
        staff.appointment_paper = record.appointment_paper.name
    staff.save()


def _staff_apply_prefill(existing, staff, user):
    """What the form opens with, preferring the application over the profile."""
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
    full_name = (f"{posted.get('first_name', '').strip()} "
                 f"{posted.get('last_name', '').strip()}").strip()
    years = _years_of_service(posted)

    if existing:
        record = _resubmit_staff_record(existing, posted, files, full_name, years)
    else:
        record = _new_staff_record(request.user, posted, files, full_name, years)
    _sync_staff_profile(staff, record, posted, years)
    return record


@_nsu_staff_required
def nsu_staff_apply(request):
    """Apply for the BiPSU Staff Scholarship."""
    from .constants import EMPLOYMENT_STATUSES

    user = request.user
    staff = _staff_profile(user)
    existing = _staff_application_for(user)

    if existing and existing.status in ('Approved', 'Pending Validation'):
        return render(request, 'nsu_staff/apply.html', {
            'blocked': True,
            'blocked_reason': ('You already have a Staff Scholarship '
                               f'application with status: {existing.status}.'),
            'existing': existing,
            'enrolled': True,
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
        'bipsu_courses': BIPSU_COURSES,
        'bipsu_schools': BIPSU_SCHOOLS,
        'employment_statuses': EMPLOYMENT_STATUSES,
        'enrolled': _nsu_staff_enrolled(user),
        'prefill': _staff_apply_prefill(existing, staff, user),
    })
