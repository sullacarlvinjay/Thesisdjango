"""The employee portal for the BiPSU Staff Scholarship.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render, redirect
from .models import STAFF_APPLICATION_DETAILS, BIPSU_SCHOOLS, BIPSU_COURSES
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
            StaffRenewal.objects.create(
                staff_user=user, supporting_document=document)
        return redirect('/nsu-staff/renewal/?submitted=1')

    return page()

@_nsu_staff_required
def nsu_staff_apply(request):
    """Apply for the BiPSU Staff Scholarship."""
    from .constants import EMPLOYMENT_STATUSES
    from .models import ApplicantRecord
    user = request.user
    staff = _staff_profile(user)

    existing = _staff_application_for(user)

    if existing and existing.status in ('Approved', 'Pending Validation'):
        return render(request, 'nsu_staff/apply.html', {
            'blocked': True,
            'blocked_reason': f'You already have a Staff Scholarship application with status: {existing.status}.',
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
        p = request.POST
        f = request.FILES

        required = {
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
        for field, label in required.items():
            if not p.get(field, '').strip():
                errors.append(f'{label} is required.')

        employment = p.get('employment_status', '').strip()
        if employment and employment != 'Regular':
            errors.append(
                'The BiPSU Staff Scholarship is open to regular employees. '
                f'Your appointment is recorded as {employment} — contact the '
                'VPSEA office if that is out of date.'
            )
        if not f.get('appointment_paper') and not (existing and existing.appointment_paper):
            errors.append('Appointment paper document is required.')

        if not errors:
            full_name = f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip()
            try:
                yos = int(p.get('years_of_service', 0) or 0)
            except (ValueError, TypeError):
                yos = 0

            if existing:
                existing.full_name = full_name or existing.full_name
                existing.contact_number = p.get('contact_number', existing.contact_number)
                existing.barangay = p.get('barangay', existing.barangay)
                existing.municipality = p.get('municipality', existing.municipality)
                existing.province = p.get('province', existing.province)
                if p.get('date_of_birth'):
                    existing.date_of_birth = p.get('date_of_birth')
                if p.get('gender'):
                    existing.gender = p.get('gender')
                if p.get('course'):
                    existing.course = p.get('course')
                if p.get('student_number'):
                    existing.student_id = p.get('student_number')
                existing.employment_status = p.get('employment_status', existing.employment_status)
                existing.designation = p.get('designation', existing.designation)
                if yos:
                    existing.years_of_service = yos
                if p.get('date_of_regularization'):
                    existing.date_of_regularization = p.get('date_of_regularization')
                existing.is_nsu_staff = True
                existing.status = 'Pending Validation'
                existing.remarks = ''
                if f.get('appointment_paper'):
                    existing.appointment_paper = f.get('appointment_paper')
                existing.save()
            else:
                existing = ApplicantRecord.objects.create(
                    full_name=full_name,
                    email=user.email,
                    contact_number=p.get('contact_number', ''),
                    barangay=p.get('barangay', ''),
                    municipality=p.get('municipality', ''),
                    province=p.get('province', ''),
                    date_of_birth=p.get('date_of_birth') or None,
                    gender=p.get('gender', ''),
                    course=p.get('course', ''),
                    year_level=int(p.get('year_level', 1) or 1),
                    student_id=p.get('student_number', ''),
                    is_nsu_staff=True,
                    employment_status=p.get('employment_status', ''),
                    designation=p.get('designation', ''),
                    years_of_service=yos or None,
                    date_of_regularization=p.get('date_of_regularization') or None,
                    appointment_paper=f.get('appointment_paper') or None,
                    qualified_for='Staff',
                    status='Pending Validation',
                )
            staff.employee_id       = p.get('student_number', '').strip() or staff.employee_id
            staff.contact_number    = p.get('contact_number', '').strip() or staff.contact_number
            staff.gender            = p.get('gender', '') or staff.gender
            staff.barangay          = p.get('barangay', '') or staff.barangay
            staff.municipality      = p.get('municipality', '') or staff.municipality
            staff.province          = p.get('province', '') or staff.province
            staff.employment_status = p.get('employment_status', '') or staff.employment_status
            staff.designation       = p.get('designation', '') or staff.designation
            if yos:
                staff.declared_years_of_service = yos
            dob, ok = _parse_date(p.get('date_of_birth', ''))
            if ok and dob:
                staff.date_of_birth = dob
            dor, ok = _parse_date(p.get('date_of_regularization', ''))
            if ok and dor:
                staff.date_of_regularization = dor
            if existing.appointment_paper:
                staff.appointment_paper = existing.appointment_paper.name
            staff.save()

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
        'prefill': {
            'first_name':   existing.full_name.split()[0] if existing and existing.full_name else user.first_name,
            'last_name':    existing.full_name.split()[-1] if existing and existing.full_name and len(existing.full_name.split()) > 1 else user.last_name,
            'date_of_birth': _pick_date(existing, staff, 'date_of_birth'),
            'gender':        _pick(existing, staff, 'gender'),
            'contact_number': _pick(existing, staff, 'contact_number'),
            'barangay':      _pick(existing, staff, 'barangay'),
            'municipality':  _pick(existing, staff, 'municipality'),
            'province':      _pick(existing, staff, 'province'),
            'student_number': (existing.student_id if existing and existing.student_id
                               else staff.employee_id),
            'year_level':    existing.year_level if existing else 1,
            'course':        existing.course if existing else '',
            'employment_status':      _pick(existing, staff, 'employment_status'),
            'designation':            _pick(existing, staff, 'designation'),
            'years_of_service':       (existing.years_of_service if existing and existing.years_of_service is not None
                                       else staff.years_of_service if staff.years_of_service is not None else ''),
            'date_of_regularization': _pick_date(existing, staff, 'date_of_regularization'),
        },
    })
