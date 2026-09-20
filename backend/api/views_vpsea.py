"""The SDSO office portal.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render, redirect
from . import scholar_columns
from .models import STAFF_APPLICATION_DETAILS, STUDENT_DETAILS, StudentProfile, Scholarship, Application, User, AcademicRenewal, ScholarshipLinkRequest, BIPSU_SCHOOLS, BIPSU_COURSES
from django.db import transaction
from . import notify
import logging
from .views_shared import _active_term, _change_own_password, _column_picker_context, _posted_custom_columns, _safe_next, _vpsea_required, paginate, record_decision
from .views_declarations import approve_declared_scholarship, approve_declared_staff_scholarship, declared_scholarships, declared_staff_scholarship, pending_declarations, reject_declared_scholarship, reject_declared_staff_scholarship
from .views_archives import STUDENT_RECORD_FIELDS, _archive_candidates

logger = logging.getLogger(__name__)


WINDOW_KINDS = {
    'applications': {
        'title': 'Application Period',
        'label': 'Applications',
        'switch': 'accepting_applications',
        'opens': 'applications_open_on',
        'days': 'applications_open_days',
    },
    'renewals': {
        'title': 'Renewal Period',
        'label': 'Renewals',
        'switch': 'accepting_renewals',
        'opens': 'renewals_open_on',
        'days': 'renewals_open_days',
    },
}

def _window_card_context(programme, kind, tab=''):
    """Context for a window card on the programme form."""
    from django.utils import timezone

    spec = WINDOW_KINDS[kind]
    today = timezone.localdate()
    named = {'kind': kind, 'title': spec['title'], 'noun': spec['label'],
             'tab': tab}
    if not programme:
        return {**named, 'programme': None}
    open_now = (programme.accepts_applications_on(today) if kind == 'applications'
                else programme.accepts_renewals_on(today))
    reason = (programme.window_closed_reason(today) if kind == 'applications'
              else programme.renewal_closed_reason(today))
    return {
        **named,
        'programme': programme,
        'accepting': getattr(programme, spec['switch']),
        'open_on': getattr(programme, spec['opens']),
        'open_days': getattr(programme, spec['days']),
        'closes_on': (programme.applications_close_on if kind == 'applications'
                      else programme.renewals_close_on),
        'is_open_now': open_now,
        'closed_reason': reason,
    }

def _save_window(request, programme, kind, back):
    """Save an application or renewal window."""
    from urllib.parse import quote

    from .models import ActivityLog

    spec = WINDOW_KINDS[kind]
    label, switch = spec['label'], spec['switch']
    opens_field, days_field = spec['opens'], spec['days']
    joiner = '&' if '?' in back else '?'
    if not programme:
        return redirect(f'{back}{joiner}error=' + quote(
            f'No programme is configured to set {label.lower()} for. '
            'Add it under Scholarship Programs first.'))

    desired = request.POST.get('set_accepting')
    if desired is not None:
        accepting = desired == '1'
        setattr(programme, switch, accepting)
        programme.save(update_fields=[switch])
        ActivityLog.record(
            request.user, f'{label} for {programme.name}: '
                       f'{"reopened" if accepting else "closed"} by hand',
            verb='other', request=request)
        return redirect(f'{back}{joiner}saved=window')

    errors = []
    opens, days = _posted_window(request.POST, errors, kind)
    if errors:
        return redirect(f'{back}{joiner}error=' + quote(' '.join(errors)))

    accepting = bool(request.POST.get(switch))
    setattr(programme, switch, accepting)
    setattr(programme, opens_field, opens)
    setattr(programme, days_field, days)
    programme.save(update_fields=[switch, opens_field, days_field])

    if not accepting:
        state = 'closed'
    elif opens:
        closes = (programme.applications_close_on if kind == 'applications'
                  else programme.renewals_close_on)
        state = f'open from {opens}' + (f' to {closes}' if closes else ' with no end date')
    else:
        state = 'open with no window'
    ActivityLog.record(
        request.user, f'{label} for {programme.name}: {state}',
        verb='other', request=request)
    return redirect(f'{back}{joiner}saved=window')

@_vpsea_required
def vpsea_affirmative_applications(request):
    """Review Affirmative Action and staff applications."""
    from .constants import DECIDED_APPLICATION_STATUSES
    from .models import ApplicantRecord, Application
    from urllib.parse import quote
    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        tab = request.POST.get('tab', 'affirmative')
        if request.POST.get('window') == 'applications':
            stype = 'Staff' if tab == 'staff' else 'Academic'
            return _save_window(
                request, Scholarship.objects.filter(type=stype).first(),
                'applications', f'/vpsea/affirmative/?tab={tab}')
        if tab == 'academic':
            try:
                acad_app = (
                    Application.objects.select_related('student')
                    .get(id=app_id)
                )
                if acad_app.status in DECIDED_APPLICATION_STATUSES:
                    return redirect('/vpsea/affirmative/?tab=academic&error=' + quote(
                        f'APP-{acad_app.id:07d} was already decided '
                        f'({acad_app.status}). A decision is made once.'))
                record_decision(
                    request, acad_app, new_status, remarks,
                    f'APP-{acad_app.id:07d} ({acad_app.scholarship.name})')
                notify.decision(
                    acad_app.student, f'Your {acad_app.scholarship.name} application',
                    new_status, remarks, link='/student/applications/',
                )
            except Application.DoesNotExist:
                pass
            return redirect('/vpsea/affirmative/?tab=academic')
        else:
            try:
                aff_app = ApplicantRecord.objects.get(id=app_id)
                if aff_app.status in DECIDED_APPLICATION_STATUSES:
                    return redirect(f'/vpsea/affirmative/?tab={tab}&error=' + quote(
                        f'{aff_app.full_name} was already decided '
                        f'({aff_app.status}). A decision is made once.'))
                record_decision(
                    request, aff_app, new_status, remarks,
                    f'the {aff_app.get_qualified_for_display()} application '
                    f'of {aff_app.full_name}')
                notify.decision(
                    aff_app.email,
                    f'Your {aff_app.get_qualified_for_display()} application',
                    new_status, remarks,
                )
                if (new_status == 'Approved'
                        and aff_app.qualified_for != 'Staff'
                        and not User.objects.filter(email=aff_app.email).exists()):
                    name_parts = aff_app.full_name.strip().split()
                    first_name = name_parts[0] if name_parts else ''
                    last_name = name_parts[-1] if len(name_parts) > 1 else ''
                    raw_password = aff_app.student_id or aff_app.email.split('@')[0]
                    new_user = User.objects.create_user(
                        username=aff_app.email,
                        email=aff_app.email,
                        password=raw_password,
                        first_name=first_name,
                        last_name=last_name,
                        role='student',
                    )
                    profile = StudentProfile.objects.create(
                        user=new_user,
                        student_id=aff_app.student_id or f'AFF-{aff_app.id}',
                        school=aff_app.school,
                        course=aff_app.course,
                        year_level=aff_app.year_level,
                        contact_number=aff_app.contact_number,
                        barangay=aff_app.barangay,
                        municipality=aff_app.municipality,
                        province=aff_app.province,
                        date_of_birth=aff_app.date_of_birth,
                        gender=aff_app.gender,
                    )
                    scholarship = Scholarship.objects.filter(type=aff_app.qualified_for).first()
                    if scholarship:
                        Application.objects.create(
                            student=profile,
                            scholarship=scholarship,
                            status='Approved',
                            remarks=remarks,
                            form_data={},
                        )
            except ApplicantRecord.DoesNotExist:
                pass
            return redirect(f'/vpsea/affirmative/?tab={tab}')

    tab = request.GET.get('tab', 'academic')
    if tab not in ('academic', 'staff'):
        tab = 'academic'
    academic_apps = (
        Application.objects
        .select_related('student__user', 'scholarship', 'reviewed_by', *STUDENT_DETAILS)
        .prefetch_related('documents')
        .exclude(scholarship__type__in=['Staff'])
        .order_by('-submitted_at')
    )
    staff_apps = ApplicantRecord.objects.filter(
        qualified_for='Staff').select_related(
            'reviewed_by', *STAFF_APPLICATION_DETAILS).order_by('-submitted_at')
    return render(request, 'vpsea/affirmative.html', {
        'academic_apps': academic_apps,
        'staff_apps': staff_apps,
        'active_tab': tab,
        'saved': request.GET.get('saved'),
        **_window_card_context(
            Scholarship.objects.filter(
                type='Staff' if tab == 'staff' else 'Academic').first(),
            'applications', tab),
    })

@_vpsea_required
def vpsea_dashboard(request):
    """The SDSO portal's landing page."""
    from .models import Application, AcademicRenewal, ApplicantRecord, SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    active_semester = parsed['semester']
    apps = Application.objects.filter(term_label=settings_obj.academic_year)
    ctx = {
        'total_applicants': apps.count(),
        'approved': apps.filter(status='Approved').count(),
        'rejected': apps.filter(status='Rejected').count(),
        'pending': apps.filter(status='Pending Validation').count(),
        'renewals': AcademicRenewal.objects.filter(status='Pending').count(),
        'pending_staff': ApplicantRecord.objects.filter(qualified_for='Staff', status='Pending Validation').count(),
        'pending_affirmative': ApplicantRecord.objects.filter(qualified_for='Affirmative', status='Pending Validation').count(),
        'active_sy_display': f"{active_sy} — {active_semester}",
    }
    return render(request, 'vpsea/dashboard.html', ctx)

@_vpsea_required
def vpsea_renewals(request):
    """Review renewal submissions."""
    if request.method == 'POST':
        from .models import SystemSettings
        if request.POST.get('window') == 'renewals':
            return _save_window(
                request, Scholarship.objects.filter(type='Academic').first(),
                'renewals', '/vpsea/renewals/')
        renewal_id = request.POST.get('renewal_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        reviewed = AcademicRenewal.objects.select_related('student__user', *STUDENT_DETAILS).filter(id=renewal_id).first()
        if reviewed:
            record_decision(
                request, reviewed, new_status, remarks,
                f'the {reviewed.get_scholarship_type_display()} renewal '
                f'of {reviewed.student}')
            notify.decision(
                reviewed.student,
                f'Your {reviewed.get_scholarship_type_display()} renewal',
                new_status, remarks,
                link='/student/renewal/academic/',
            )
        if new_status == 'Approved':
            try:
                renewal = AcademicRenewal.objects.select_related('student').get(id=renewal_id)
                scholarship = Scholarship.objects.filter(
                    type=renewal.scholarship_type).first()
                if scholarship:
                    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
                    parsed = SystemSettings.parse_label(settings_obj.academic_year)
                    already = Application.objects.filter(
                        student=renewal.student, scholarship=scholarship,
                        school_year=parsed['sy'], semester=parsed['semester'],
                    ).exists()
                    if not already:
                        Application.objects.create(
                            student=renewal.student,
                            scholarship=scholarship,
                            status='Approved',
                            remarks=remarks,
                            source='renewal',
                            school_year=parsed['sy'],
                            semester=parsed['semester'],
                            form_data={'renewal_id': renewal_id},
                        )
            except AcademicRenewal.DoesNotExist:
                pass
        return redirect('/vpsea/renewals/')
    renewals = AcademicRenewal.objects.select_related(
        'student__user', 'reviewed_by', *STUDENT_DETAILS).order_by('-submitted_at')
    return render(request, 'vpsea/renewals.html', {
        'renewals': renewals,
        'approved_count': renewals.filter(status='Approved').count(),
        'pending_count': renewals.filter(status='Pending').count(),
        'saved': request.GET.get('saved'),
        'error': request.GET.get('error'),
        **_window_card_context(
            Scholarship.objects.filter(type='Academic').first(), 'renewals'),
    })

@_vpsea_required
def vpsea_announcements(request):
    """Write and publish announcements."""
    from .models import Announcement
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        body = (request.POST.get('body') or '').strip()
        if not title or not body:
            return redirect('/vpsea/announcements/?error=1')
        Announcement.objects.create(title=title, body=body, published_by=request.user)
        reached = notify.broadcast(title, body)
        return redirect(f'/vpsea/announcements/?posted={reached}')
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'vpsea/announcements.html', {'announcements': announcements})

def _decide_added_scholarship(request):
    """Accept or refuse an award the office added by hand."""
    from urllib.parse import quote
    from .models import ImportedScholar, SystemSettings

    req = pending_declarations().filter(
        id=request.POST.get('declaration_id')).first()
    if not req:
        return redirect('/vpsea/accounts/?error=That+scholarship+is+no+longer+'
                        'waiting+for+a+decision')

    action = request.POST.get('action')
    message = request.POST.get('message', '').strip()

    if action == 'reject':
        if not message:
            return redirect('/vpsea/accounts/?error=Say+why+before+turning+a+'
                            'scholarship+down.+Your+reason+is+the+only+thing+'
                            'the+student+is+told')
        reject_declared_scholarship(req, request.user, message)
        return redirect('/vpsea/accounts/?scholarship=rejected')

    if action != 'approve':
        return redirect('/vpsea/accounts/')

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    archive = None
    archive_id = request.POST.get(f'archive_id_{req.pk}', '').strip()
    if archive_id:
        archive = ImportedScholar.objects.filter(
            id=archive_id, scholarship_type=req.scholarship_type,
            term_label=settings_obj.academic_year, claimed_by__isnull=True,
        ).first()
        if not archive:
            return redirect('/vpsea/accounts/?error=That+archive+row+is+no+'
                            'longer+available')

    _award, problem = approve_declared_scholarship(
        req, request.user, archive=archive, remarks=message,
        tier=request.POST.get(f'award_tier_{req.pk}', ''))
    if problem:
        return redirect(f'/vpsea/accounts/?error={quote(problem)}')
    return redirect('/vpsea/accounts/?scholarship=approved')

def _claimed_archive_row(request, declared):
    """The imported row a declaration is being matched to.

    Returns:
        ``(row, problem)``. A blank choice is not a problem — it means the
        office is approving the declaration without matching it to an
        imported scholar.
    """
    archive_id = request.POST.get(f'archive_id_{declared.pk}', '').strip()
    if not archive_id:
        return None, ''

    from .models import ImportedScholar, SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    row = ImportedScholar.objects.filter(
        id=archive_id, scholarship_type=declared.scholarship_type,
        term_label=settings_obj.academic_year, claimed_by__isnull=True,
    ).first()
    if not row:
        return None, 'That archive row is no longer available'
    return row, ''


def _decide_declarations(request, account, action, message):
    """Approve or reject everything this account declared.

    Returns a problem to show the office, or '' when all of it went through.
    """
    staff_declared = declared_staff_scholarship(account)
    if staff_declared and action == 'approve':
        _award, problem = approve_declared_staff_scholarship(
            staff_declared, request.user, remarks=message)
        if problem:
            return problem
    elif staff_declared:
        reject_declared_staff_scholarship(staff_declared, request.user, message)

    for declared in declared_scholarships(getattr(account, 'profile', None)):
        if action != 'approve':
            reject_declared_scholarship(declared, request.user, message)
            continue
        archive, problem = _claimed_archive_row(request, declared)
        if problem:
            return problem
        _award, problem = approve_declared_scholarship(
            declared, request.user, archive=archive, remarks=message,
            tier=request.POST.get(f'award_tier_{declared.pk}', ''))
        if problem:
            return problem
    return ''


ACCOUNTS_BACK = '/vpsea/accounts/'

MIN_PASSWORD = 8


def _office_error(message):
    """Send the office back to the accounts page with one message."""
    from urllib.parse import quote

    return redirect(f'{ACCOUNTS_BACK}?error={quote(message)}')


def _office_saved(email, what):
    """Send the office back having changed one office account."""
    from urllib.parse import quote

    return redirect(f'{ACCOUNTS_BACK}?office={what}&who={quote(email)}')


def _office_accounts():
    """Every account that signs into this portal, oldest first."""
    return User.objects.filter(role='vpsea').order_by('date_joined')


def _may_manage_office(user):
    """Whether this office account may open and close the others.

    The line is not rank but recovery. An account that reaches the Django
    admin can put back anything that goes wrong here; an account opened from
    this panel cannot, and is not given the power to lock out the one that
    opened it. Both accounts reach the same scholarship work either way.
    """
    return bool(user.is_superuser)


def _refuse_office_management():
    """Turn away an office account that may not manage the others."""
    return _office_error('Your account signs in to this portal but may not open '
                         'or close another one. Ask whoever opened yours.')


def _create_office_account(request):
    """Open a second login onto this portal.

    The new account is the same role as the one creating it, so it reaches
    the same pages and is held to the same MFA rule. What separates the two
    is not what they may do but that every decision now records which of them
    made it.
    """
    from .models import ActivityLog

    if not _may_manage_office(request.user):
        return _refuse_office_management()

    first_name = (request.POST.get('first_name') or '').strip()
    last_name = (request.POST.get('last_name') or '').strip()
    email = (request.POST.get('email') or '').strip().lower()
    password = request.POST.get('password') or ''

    errors = []
    if not first_name:
        errors.append('A name is required — it is what the audit trail reads back.')
    if not email:
        errors.append('An email address is required — it is how they sign in.')
    if len(password) < MIN_PASSWORD:
        errors.append(f'The password must be at least {MIN_PASSWORD} characters.')
    if email and User.objects.filter(email__iexact=email).exists():
        errors.append(f'{email} already has an account.')
    if errors:
        return _office_error(' '.join(errors))

    account = User.objects.create_user(
        username=email, email=email, password=password, role='vpsea',
        first_name=first_name, last_name=last_name,
    )
    ActivityLog.record(
        request.user, f'Created the office account {email}',
        verb='create', target=account, request=request)
    return _office_saved(email, 'created')


def _office_account(request):
    """The office account this POST names, or ``None``."""
    return _office_accounts().filter(pk=request.POST.get('account_id')).first()


def _reset_office_password(request):
    """Set a new password on another office account."""
    from .models import ActivityLog

    if not _may_manage_office(request.user):
        return _refuse_office_management()

    account = _office_account(request)
    password = request.POST.get('password') or ''
    if not account:
        return _office_error('That is not an office account.')
    if account == request.user:
        return _office_error('Change your own password from My Profile, so that '
                             'you are asked for the current one first.')
    if len(password) < MIN_PASSWORD:
        return _office_error(f'The password must be at least {MIN_PASSWORD} characters.')

    account.set_password(password)
    account.save(update_fields=['password'])
    ActivityLog.record(
        request.user, f'Reset the password for the office account {account.email}',
        verb='update', target=account, request=request)
    return _office_saved(account.email, 'reset')


def _set_office_access(request):
    """Close or reopen another office account.

    Closed, never deleted. Every decision this account reached points at it,
    and deleting the row would leave that history attributed to nobody.
    """
    from .models import ActivityLog

    if not _may_manage_office(request.user):
        return _refuse_office_management()

    account = _office_account(request)
    if not account:
        return _office_error('That is not an office account.')
    if account == request.user:
        return _office_error('An office account cannot close itself.')

    wanted = request.POST.get('active') == '1'
    if not wanted and _office_accounts().filter(is_active=True).count() < 2:
        return _office_error('That is the last office account that can still sign '
                             'in. Open another one before closing this one.')

    account.is_active = wanted
    account.save(update_fields=['is_active'])
    what = 'Reopened' if wanted else 'Closed'
    ActivityLog.record(
        request.user, f'{what} the office account {account.email}',
        verb='update', target=account, request=request,
        changes={'is_active': [str(not wanted), str(wanted)]})
    return _office_saved(account.email, 'reopened' if wanted else 'closed')


def _decide_account(request):
    """Approve or reject one registration, with everything it declared."""
    from urllib.parse import quote

    from .models import ActivityLog

    account = User.objects.filter(
        id=request.POST.get('user_id'), role__in=('student', 'nsu_staff'),
    ).first()
    if not account:
        return redirect('/vpsea/accounts/?error=Account+not+found')

    action = request.POST.get('action')
    message = request.POST.get('message', '').strip()
    if action not in ('approve', 'reject'):
        return redirect('/vpsea/accounts/?error=Unknown+action')
    if action == 'reject' and not message:
        return redirect('/vpsea/accounts/?error=A+reason+is+required+when+rejecting'
                        '+—+it+is+what+the+person+reads+when+they+try+to+sign+in')

    problem = _decide_declarations(request, account, action, message)
    if problem:
        return redirect(f'/vpsea/accounts/?error={quote(problem)}')

    status = 'approved' if action == 'approve' else 'rejected'
    was = account.verification_status
    account.decide_verification(status, message, request.user)

    _in_app, emailed = notify.account_decision(
        account, status, account.verification_note)
    ActivityLog.record(
        request.user,
        f'Account {status}: {account.get_full_name() or account.email} '
        f'({account.get_role_display()}) — {account.verification_note}',
        verb='approve' if status == 'approved' else 'reject',
        target=account, request=request,
        changes={'verification_status': [was, status]})
    return redirect(f'/vpsea/accounts/?{action}d=1&emailed={1 if emailed else 0}')


def _attach_profiles(accounts):
    """Hang each account's student and employee profile off the row."""
    from .models import StaffProfile, StudentProfile

    students = {p.user_id: p for p in
                StudentProfile.with_details().filter(user__in=accounts)}
    staff = {p.user_id: p for p in
             StaffProfile.objects.filter(user__in=accounts)}
    for account in accounts:
        account.student_profile = students.get(account.id)
        account.employee_profile = staff.get(account.id)


def _attach_archive_candidates(declarations, active_label):
    """Hang the imported rows each declaration might be claiming off it."""
    for declared in declarations:
        declared.archive_candidates = list(
            _archive_candidates(declared, active_label))
        declared.other_semester_rows = list(
            _archive_candidates(declared).exclude(term_label=active_label)[:5])


def _duplicate_benefit_warning(account, active_label):
    """The hazard in approving this registration, in one sentence, or ''.

    Statement of the Problem #7 is duplicate benefits. They are recorded
    rather than refused — the office has to be able to see one to act on it —
    so the place to stop a mistake is the moment before it is made.
    """
    from .constants import CONFLICTING_BENEFIT_TYPES
    from .models import Application

    declared = {d.scholarship_type for d in getattr(account, 'declarations', [])}
    clashing = sorted(declared & CONFLICTING_BENEFIT_TYPES)
    profile = getattr(account, 'student_profile', None)

    held = []
    if profile is not None:
        held = sorted(
            Application.objects
            .filter(student=profile, status='Approved', term_label=active_label,
                    scholarship__type__in=CONFLICTING_BENEFIT_TYPES)
            .values_list('scholarship__type', flat=True).distinct())

    if held and clashing:
        return (f'This account already holds {", ".join(held)} for '
                f'{active_label}. Approving adds {", ".join(clashing)} on top '
                'of it — a duplicate government benefit.')
    if len(clashing) > 1:
        return (f'{", ".join(clashing)} are all national grants and are not '
                'meant to be held together. Approving records every one of '
                'them against this student.')
    return ''


def _attach_pending_declarations(pending, active_label):
    """Hang each waiting registrant's declarations off their row."""
    for account in pending:
        account.staff_declared = declared_staff_scholarship(account)
        account.declarations = declared_scholarships(account.student_profile)
        _attach_archive_candidates(account.declarations, active_label)
        account.duplicate_benefit_warning = _duplicate_benefit_warning(
            account, active_label)


def _attach_decided_declarations(decided):
    """Hang each decided registrant's declarations off their row.

    Read in two queries rather than per row: the decided list is the one
    that keeps growing, and a query per account is what made this page slow.
    """
    from collections import defaultdict

    from .models import StaffScholarshipDeclaration

    per_student = defaultdict(list)
    for declared in (ScholarshipLinkRequest.objects
                     .select_related('reviewed_by', 'matched_archive')
                     .filter(student__user__in=decided, filed_in_portal=False)
                     .order_by('submitted_at', 'pk')):
        per_student[declared.student_id].append(declared)

    per_employee = {}
    for declaration in (StaffScholarshipDeclaration.objects
                        .select_related('reviewed_by')
                        .filter(staff_user__in=decided).order_by('submitted_at')):
        per_employee[declaration.staff_user_id] = declaration

    for account in decided:
        account.staff_declared = per_employee.get(account.id)
        account.declarations = per_student.get(
            getattr(account.student_profile, 'pk', None), [])


@_vpsea_required
def vpsea_accounts(request):
    """The account verification queue.

    Both queues are paged: the pending list used to be read whole and then
    queried again per row for each registrant's declarations, which is
    survivable at a demo's handful of accounts and not at a few years of
    intake.
    """
    from django.conf import settings as django_settings

    from .models import CHED_TIER_CHOICES, SystemSettings

    if request.method == 'POST':
        office = request.POST.get('office')
        if office == 'create':
            return _create_office_account(request)
        if office == 'reset':
            return _reset_office_password(request)
        if office == 'access':
            return _set_office_access(request)
        if request.POST.get('declaration_id'):
            return _decide_added_scholarship(request)
        return _decide_account(request)

    pending_page = paginate(request, User.objects.filter(
        verification_status='pending', role__in=('student', 'nsu_staff'),
    ).order_by('date_joined'), param='pending_page')
    pending = pending_page['rows']

    decided_page = paginate(request, User.objects.filter(
        verification_status__in=('approved', 'rejected'),
        role__in=('student', 'nsu_staff'), verified_at__isnull=False,
    ).select_related('verified_by').order_by('-verified_at'),
        param='decided_page')
    decided = decided_page['rows']

    _attach_profiles(pending + decided)

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    _attach_pending_declarations(pending, active_label)
    _attach_decided_declarations(decided)

    settings_obj.refresh_from_db()
    added = list(pending_declarations())
    _attach_archive_candidates(added, active_label)

    return render(request, 'vpsea/accounts.html', {
        'active': 'accounts',
        'pending': pending,
        'pending_page': pending_page,
        'decided': decided,
        'decided_page': decided_page,
        'added_scholarships': added,
        'scholarship_decision': request.GET.get('scholarship', ''),
        'ched_tiers': CHED_TIER_CHOICES,
        'active_label': active_label,
        'error': request.GET.get('error', ''),
        'approved': request.GET.get('approved'),
        'rejected': request.GET.get('rejected'),
        'emailed': request.GET.get('emailed'),
        'email_enabled': django_settings.EMAIL_ENABLED,
        'office_accounts': _office_accounts(),
        'may_manage_office': _may_manage_office(request.user),
        'office_done': request.GET.get('office', ''),
        'office_who': request.GET.get('who', ''),
        'min_password': MIN_PASSWORD,
    })

def _mfa_context(user, **extra):
    """What the profile page needs to show about the second factor."""
    from django.conf import settings

    from . import mfa

    context = {
        'mfa_enabled': user.mfa_enabled,
        'mfa_enforced': getattr(settings, 'MFA_ENFORCED', False),
        'mfa_required': user.mfa_required,
        'mfa_recovery_left': len(user.mfa_recovery_codes or []),
        'mfa_enrolling': bool(user.mfa_secret) and not user.mfa_enabled,
        'mfa_secret': mfa.format_secret(user.mfa_secret) if user.mfa_secret else '',
        'mfa_uri': (mfa.provisioning_uri(user.mfa_secret, user.email)
                    if user.mfa_secret else ''),
    }
    context.update(extra)
    return context


def _handle_mfa_action(request, user, action):
    """Start, confirm or drop this account's second factor.

    Returns a response, or ``None`` when the post was not an MFA one.
    """
    from .models import ActivityLog

    if action == 'mfa_start':
        user.begin_mfa_enrolment()
        return redirect('/vpsea/profile/?mfa=enrol')

    if action == 'mfa_confirm':
        codes = user.confirm_mfa(request.POST.get('mfa_code'))
        if codes is None:
            return render(request, 'vpsea/profile.html', dict(_mfa_context(user), **{
                'active': 'profile',
                'errors': ['That code did not match. Check that the app is set '
                           'up against this account and read the current code.'],
            }))
        ActivityLog.record(
            user, 'Turned on two-step sign-in for their own account',
            verb='update', request=request)
        return render(request, 'vpsea/profile.html', dict(_mfa_context(user), **{
            'active': 'profile',
            'errors': [],
            'mfa_new_recovery_codes': codes,
        }))

    if action == 'mfa_disable':
        if not user.check_password(request.POST.get('current_password') or ''):
            return render(request, 'vpsea/profile.html', dict(_mfa_context(user), **{
                'active': 'profile',
                'errors': ['Enter your current password to turn two-step '
                           'sign-in off.'],
            }))
        user.disable_mfa()
        ActivityLog.record(
            user, 'Turned off two-step sign-in for their own account',
            verb='update', request=request)
        return redirect('/vpsea/profile/?mfa=off')

    return None


@_vpsea_required
def vpsea_profile(request):
    """The office's own profile, password and second factor."""
    from . import email_verify
    from .models import ActivityLog

    user = request.user
    errors = []
    saved = password_changed = email_changed = False

    if request.method == 'POST':
        response = _handle_mfa_action(request, user, request.POST.get('action'))
        if response is not None:
            return response
        wanted_password = bool(request.POST.get('new_password') or
                               request.POST.get('current_password'))
        old_email = user.email
        new_email = (request.POST.get('email') or old_email).strip()
        wanted_email = new_email.lower() != old_email.lower()
        if wanted_email:
            problem = email_verify.address_error(new_email)
            if problem:
                errors.append(problem)
            elif len(new_email) > 150:
                errors.append('That email address is too long to sign in with. '
                              'Keep it under 150 characters.')
            elif User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                errors.append(f'{new_email} already signs another account in. '
                              'Two accounts cannot share an address.')
        if not errors:
            errors = _change_own_password(request, user)
        if not errors:
            user.first_name = (request.POST.get('first_name') or user.first_name).strip()
            user.last_name = (request.POST.get('last_name') or user.last_name).strip()
            user.email = new_email
            user.username = new_email
            if request.FILES.get('photo'):
                user.photo = request.FILES['photo']
            user.save(update_fields=['first_name', 'last_name', 'email',
                                     'username', 'photo'])
            if wanted_email:
                ActivityLog.record(
                    user, f'Changed their own sign-in email from {old_email} '
                               f'to {new_email}',
                    verb='update', request=request)
            saved = True
            password_changed = wanted_password
            email_changed = wanted_email

    return render(request, 'vpsea/profile.html', dict(_mfa_context(user), **{
        'active': 'profile',
        'saved': saved,
        'password_changed': password_changed,
        'email_changed': email_changed,
        'errors': errors,
        'mfa_notice': request.GET.get('mfa', ''),
    }))

@_vpsea_required
def vpsea_students(request):
    """Scholar and non-scholar student lists."""
    from .models import StudentProfile, Application, SystemSettings
    from django.db.models import Q

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    parsed = SystemSettings.parse_label(active_label)
    current_sy = parsed['sy']
    current_sem = parsed['semester']

    q = request.GET.get('q', '').strip()
    stype = request.GET.get('stype', '').strip()

    scholarship_types = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']

    students = (StudentProfile.objects
                .select_related('user', *StudentProfile.DETAIL_RELATIONS)
                .order_by('user__last_name'))
    if active_label:
        students = students.filter(
            applications__status='Approved',
            applications__term_label=active_label,
        ).distinct()
    else:
        students = students.filter(applications__status='Approved').distinct()

    if q:
        students = students.filter(
            Q(user__last_name__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(student_id__icontains=q)
        )

    if stype:
        if stype in ('Affirmative', 'Staff'):
            from .models import ApplicantRecord
            aff_emails = ApplicantRecord.objects.filter(
                qualified_for=stype, status='Approved'
            ).values_list('email', flat=True)
            students = students.filter(user__email__in=aff_emails)
        else:
            students = students.filter(
                applications__scholarship__type=stype
            ).distinct()

    approved_pks = Application.objects.filter(
        status='Approved'
    ).values_list('student_id', flat=True).distinct()

    no_scholarship_qs = (
        StudentProfile.objects
        .select_related('user', *StudentProfile.DETAIL_RELATIONS)
        .exclude(pk__in=approved_pks)
        .filter(user__verification_status='approved')
        .order_by('user__last_name', 'user__first_name')
    )
    if q:
        no_scholarship_qs = no_scholarship_qs.filter(
            Q(user__last_name__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(student_id__icontains=q)
        )

    tab = request.GET.get('tab', 'scholars')

    scholars_page = paginate(request, students, param='scholars_page')
    unawarded_page = paginate(request, no_scholarship_qs,
                              param='unawarded_page')

    return render(request, 'vpsea/students.html', {
        'students': scholars_page['rows'],
        'scholars_page': scholars_page,
        'no_scholarship_students': unawarded_page['rows'],
        'unawarded_page': unawarded_page,
        'q': q,
        'stype': stype,
        'tab': tab,
        'scholarship_types': scholarship_types,
        'current_sy': current_sy,
        'current_sem': current_sem,
    })

@_vpsea_required
def vpsea_student_add(request):
    """Add a student record by hand."""
    from .models import StudentProfile, Scholarship, Application, ApplicationDocument
    from .constants import CIVIL_STATUSES, SEMESTERS, STUDENT_LEVELS
    errors = []
    if request.method == 'POST':
        p = request.POST
        f = request.FILES
        email = p.get('email', '').strip()
        student_id = p.get('student_id', '').strip()
        if User.objects.filter(email=email).exists():
            errors.append('Email already registered.')
        if StudentProfile.objects.filter(student_id=student_id).exists():
            errors.append('Student ID already registered.')
        if not errors:
            user = User.objects.create_user(
                username=email, email=email,
                password=p.get('password') or student_id,
                first_name=p.get('first_name', ''),
                last_name=p.get('last_name', ''),
                role='student',
            )
            profile = StudentProfile.objects.create(
                user=user,
                student_id=student_id,
                middle_name=p.get('middle_name', '').strip(),
                suffix=p.get('suffix', '').strip(),
                school=p.get('school', ''),
                course=p.get('course', ''),
                year_level=int(p.get('year_level', 1)),
                gwa=float(p.get('gwa', 0) or 0),
                contact_number=p.get('contact_number', ''),
                barangay=p.get('barangay', ''),
                municipality=p.get('municipality', ''),
                province=p.get('province', ''),
                date_of_birth=p.get('date_of_birth') or None,
                gender=p.get('gender', ''),
                family_income=float(p.get('family_income', 0) or 0),
                **_enrollment_fields(p),
            )
            form_data = {
                k: v for k, v in p.items()
                if k not in ('csrfmiddlewaretoken',) + STUDENT_RECORD_FIELDS
            }
            scholarship = Scholarship.objects.filter(type='Academic').first()
            if scholarship:
                app = Application.objects.create(
                    student=profile, scholarship=scholarship,
                    status='Approved', form_data=form_data,
                )
                doc_fields = ['doc_certificate_of_grades', 'doc_certificate_of_enrollment',
                              'doc_prospectus', 'doc_id_photo', 'doc_application_form']
                for field in doc_fields:
                    uploaded = f.get(field)
                    if uploaded:
                        ApplicationDocument.objects.create(
                            application=app, name=field.replace('doc_', '').replace('_', ' ').title(),
                            file=uploaded,
                        )
            return redirect('/vpsea/students/?added=1')
    import json

    active_term = _active_term()

    return render(request, 'vpsea/student_form.html', {'errors': errors, 'action': 'Add', 'form_data': request.POST, 'doc_list': _doc_list(),
        'show_application_fields': True,
        'cancel_url': _safe_next(request, '/vpsea/students/'),

        'bipsu_schools': BIPSU_SCHOOLS, 'bipsu_courses_json': json.dumps(BIPSU_COURSES),
        'v_first_name': request.POST.get('first_name', ''),
        'v_last_name': request.POST.get('last_name', ''),
        'v_middle_name': request.POST.get('middle_name', ''),
        'v_suffix': request.POST.get('suffix', ''),
        'v_school': request.POST.get('school', ''),
        'v_email': request.POST.get('email', ''),
        'v_student_id': request.POST.get('student_id', ''),
        'v_course': request.POST.get('course', ''),
        'v_year_level': request.POST.get('year_level', '1'),
        'v_gwa': request.POST.get('gwa', ''),
        'v_gender': request.POST.get('gender', ''),
        'v_date_of_birth': request.POST.get('date_of_birth', ''),
        'v_contact_number': request.POST.get('contact_number', ''),
        'v_barangay': request.POST.get('barangay', ''),
        'v_municipality': request.POST.get('municipality', ''),
        'v_province': request.POST.get('province', ''),
        'v_family_income': request.POST.get('family_income', ''),
        'v_birth_place': request.POST.get('birth_place', ''),
        'v_civil_status': request.POST.get('civil_status', ''),
        'v_level': request.POST.get('level', ''),
        'v_department': request.POST.get('department', ''),
        'v_curriculum': request.POST.get('curriculum', ''),
        'v_learner_ref_no': request.POST.get('learner_ref_no', ''),
        'v_entry_period': request.POST.get('entry_period', ''),
        'v_entry_date': request.POST.get('entry_date', ''),
        'v_exam_score': request.POST.get('exam_score', ''),
        'civil_statuses': CIVIL_STATUSES, 'student_levels': STUDENT_LEVELS,
        'semesters': SEMESTERS,
        'v_elementary': request.POST.get('elementary', ''),
        'v_highschool': request.POST.get('highschool', ''),
        'v_last_school': request.POST.get('last_school', ''),
        'v_father_name': request.POST.get('father_name', ''),
        'v_father_occupation': request.POST.get('father_occupation', ''),
        'v_mother_name': request.POST.get('mother_name', ''),
        'v_mother_occupation': request.POST.get('mother_occupation', ''),
        'v_semester': request.POST.get('semester', active_term['semester']),
        'v_school_year': request.POST.get('school_year', active_term['sy']),
    })

@_vpsea_required
def vpsea_student_edit(request, pk):
    """Edit a student record."""
    from .models import StudentProfile, Application, ApplicationDocument
    from .constants import CIVIL_STATUSES, SEMESTERS, STUDENT_LEVELS
    try:
        profile = StudentProfile.objects.select_related('user').get(pk=pk)
    except StudentProfile.DoesNotExist:
        return redirect('/vpsea/students/')

    app = Application.objects.filter(
        student=profile, scholarship__type='Academic'
    ).prefetch_related('documents').order_by('-submitted_at').first()

    errors = []
    if request.method == 'POST':
        p = request.POST
        f = request.FILES
        u = profile.user
        new_email = p.get('email', '').strip()
        if new_email != u.email and User.objects.filter(email=new_email).exists():
            errors.append('Email already in use by another account.')
        new_sid = p.get('student_id', '').strip()
        if new_sid != profile.student_id and StudentProfile.objects.filter(student_id=new_sid).exists():
            errors.append('Student ID already in use.')
        if not errors:
            u.first_name = p.get('first_name', '')
            u.last_name = p.get('last_name', '')
            u.email = new_email
            u.username = new_email
            if p.get('password'):
                u.set_password(p.get('password'))
            u.save()
            profile.student_id = new_sid
            profile.middle_name = p.get('middle_name', profile.middle_name).strip()
            profile.suffix = p.get('suffix', profile.suffix).strip()
            profile.school = p.get('school', profile.school)
            profile.course = p.get('course', '')
            profile.year_level = int(p.get('year_level', 1))
            profile.gwa = float(p.get('gwa', 0) or 0)
            profile.contact_number = p.get('contact_number', '')
            profile.barangay = p.get('barangay', '')
            profile.municipality = p.get('municipality', '')
            profile.province = p.get('province', '')
            profile.date_of_birth = p.get('date_of_birth') or None
            profile.gender = p.get('gender', '')
            profile.family_income = float(p.get('family_income', 0) or 0)
            for field, value in _enrollment_fields(p, profile).items():
                setattr(profile, field, value)
            profile.save()
            if app:
                form_data = dict(app.form_data)
                for k, v in p.items():
                    if k not in ('csrfmiddlewaretoken',) + STUDENT_RECORD_FIELDS:
                        form_data[k] = v
                app.form_data = form_data
                app.save()
                doc_fields = ['doc_certificate_of_grades', 'doc_certificate_of_enrollment',
                              'doc_prospectus', 'doc_id_photo', 'doc_application_form']
                for field in doc_fields:
                    uploaded = f.get(field)
                    if uploaded:
                        label = field.replace('doc_', '').replace('_', ' ').title()
                        app.documents.filter(name=label).delete()
                        ApplicationDocument.objects.create(
                            application=app, name=label, file=uploaded,
                        )
            return redirect('/vpsea/students/?edited=1')
    fd = request.POST if request.method == 'POST' else {}
    afd = (app.form_data or {}) if app else {}
    active_term = _active_term()
    import json
    return render(request, 'vpsea/student_form.html', {
        'errors': errors, 'action': 'Edit',
        'profile': profile, 'app': app,
        'show_application_fields': app is not None,
        'cancel_url': _safe_next(request, '/vpsea/students/'),
        'form_data': fd,
        'doc_list': _doc_list(),
        'bipsu_schools': BIPSU_SCHOOLS, 'bipsu_courses_json': json.dumps(BIPSU_COURSES),
        'v_first_name': fd.get('first_name', profile.user.first_name),
        'v_last_name': fd.get('last_name', profile.user.last_name),
        'v_middle_name': fd.get('middle_name', profile.middle_name),
        'v_suffix': fd.get('suffix', profile.suffix),
        'v_school': fd.get('school', profile.school),
        'v_email': fd.get('email', profile.user.email),
        'v_student_id': fd.get('student_id', profile.student_id),
        'v_course': fd.get('course', profile.course),
        'v_year_level': fd.get('year_level', str(profile.year_level)),
        'v_gwa': fd.get('gwa', str(profile.gwa)),
        'v_gender': fd.get('gender', profile.gender),
        'v_date_of_birth': fd.get('date_of_birth', profile.date_of_birth.strftime('%Y-%m-%d') if profile.date_of_birth else ''),
        'v_contact_number': fd.get('contact_number', profile.contact_number),
        'v_barangay': fd.get('barangay', profile.barangay),

        'v_municipality': fd.get('municipality', profile.municipality),

        'v_province': fd.get('province', profile.province),
        'v_family_income': fd.get('family_income', str(profile.family_income)),
        'v_birth_place': fd.get('birth_place', profile.birth_place),
        'v_level': fd.get('level', profile.level),
        'v_department': fd.get('department', profile.department),
        'v_curriculum': fd.get('curriculum', profile.curriculum),
        'v_learner_ref_no': fd.get('learner_ref_no', profile.learner_ref_no),
        'v_entry_period': fd.get('entry_period', profile.entry_period),
        'v_entry_date': fd.get('entry_date', profile.entry_date.strftime('%Y-%m-%d') if profile.entry_date else ''),
        'v_exam_score': fd.get('exam_score', '' if profile.exam_score is None else profile.exam_score),
        'civil_statuses': CIVIL_STATUSES, 'student_levels': STUDENT_LEVELS,
        'semesters': SEMESTERS,
        'v_elementary': fd.get('elementary', profile.elementary or afd.get('elementary', '')),
        'v_highschool': fd.get('highschool', profile.highschool or afd.get('highschool', '')),
        'v_last_school': fd.get('last_school', profile.last_school or afd.get('last_school', '')),
        'v_father_name': fd.get('father_name', profile.father_name or afd.get('father_name', '')),
        'v_father_occupation': fd.get('father_occupation', profile.father_occupation or afd.get('father_occupation', '')),
        'v_mother_name': fd.get('mother_name', profile.mother_name or afd.get('mother_name', '')),
        'v_mother_occupation': fd.get('mother_occupation', profile.mother_occupation or afd.get('mother_occupation', '')),
        'v_semester': fd.get('semester', afd.get('semester', active_term['semester'])),
        'v_school_year': fd.get('school_year', afd.get('school_year', active_term['sy'])),
        'v_civil_status': fd.get('civil_status', profile.civil_status),
        'v_citizenship': profile.citizenship,
        'v_household_size': profile.household_size,
        'v_year_first_enrolled': profile.year_first_enrolled,
        'v_is_listahanan': profile.is_listahanan_household,
        'v_is_4ps': profile.is_4ps_beneficiary,
        'v_has_previous_degree': profile.has_previous_degree,
        'v_is_solo_parent': profile.is_solo_parent_dependent,
        'v_disability_type': profile.disability_type,
        'v_is_pwd': profile.is_pwd,
        'v_indigenous_group': profile.indigenous_group,
        'v_shs_gpa': profile.shs_gpa,
        'v_suc_exam_score': profile.suc_exam_display or profile.suc_exam_score,
        'v_is_tes_beneficiary': profile.is_tes_beneficiary,
    })

def _enrollment_fields(p, profile=None):
    """Posted enrolment fields for a student record."""
    def current(name, default=''):
        """The value currently stored for this window field."""
        return getattr(profile, name, default) if profile is not None else default

    def number(name):
        """A positive integer from a posted window field."""
        raw = (p.get(name) or '').strip()
        if raw == '':
            return current(name, None)
        try:
            return float(raw)
        except ValueError:
            return current(name, None)

    return {
        'birth_place': p.get('birth_place', current('birth_place')),
        'civil_status': p.get('civil_status', current('civil_status')),
        'level': p.get('level', current('level')),
        'department': p.get('department', current('department')),
        'curriculum': p.get('curriculum', current('curriculum')),
        'learner_ref_no': p.get('learner_ref_no', current('learner_ref_no')),
        'entry_period': p.get('entry_period', current('entry_period')),
        'entry_date': p.get('entry_date') or current('entry_date', None),
        'exam_score': number('exam_score'),
    }

def _doc_list():
    """The documents attached to a student's application."""
    return [
        ('doc_certificate_of_grades',   'Certificate Of Grades',   'Official COG from the Registrar for the previous semester.'),
        ('doc_certificate_of_enrollment', 'Certificate Of Enrollment', 'Official COE from the Registrar for the current semester.'),
        ('doc_prospectus',              'Prospectus',              'Program prospectus or subject checklist showing enrolled subjects.'),
        ('doc_id_photo',                'Id Photo',                'Recent 2×2 ID photo with white background.'),
        ('doc_application_form',        'Application Form',        'Signed and accomplished scholarship application form.'),
    ]

@_vpsea_required
def vpsea_student_delete(request, pk):
    """Delete a student record."""
    from .models import StudentProfile
    if request.method == 'POST':
        try:
            profile = StudentProfile.objects.select_related('user').get(pk=pk)
            profile.user.delete()
        except StudentProfile.DoesNotExist:
            pass
        return redirect('/vpsea/students/?deleted=1')
    return redirect('/vpsea/students/')

@_vpsea_required
def vpsea_scholarships(request):
    """The scholarship catalogue."""
    scholarships = Scholarship.objects.all().order_by('type')
    return render(request, 'vpsea/scholarships.html', {
        'scholarships': scholarships,
        'added': request.GET.get('added'),
        'saved': request.GET.get('saved'),
    })

def _column_name_errors(posted):
    """Problems with the custom column names posted for a programme."""
    return [
        f'"{label}" is already a column the archive fills — tick it in the '
        'list above instead of adding it.'
        for label in scholar_columns.catalogue_clashes(
            posted.getlist('extra_columns'))
    ]

def _posted_logo(posted):
    """The seal chosen for a programme, validated against the folder."""
    from .constants import available_logos

    chosen = (posted.get('logo') or '').strip()
    return chosen if chosen in available_logos() else ''

def _posted_window(p, errors, kind='applications'):
    """The application or renewal window posted for a programme."""
    from datetime import date as _date

    raw_opens = (p.get(f'{kind}_open_on') or '').strip()
    raw_closes = (p.get(f'{kind}_close_on') or '').strip()
    raw_days = (p.get(f'{kind}_open_days') or '').strip()

    opens = None
    if raw_opens:
        try:
            opens = _date.fromisoformat(raw_opens)
        except ValueError:
            errors.append('The opening date must be a real date, as YYYY-MM-DD.')

    if raw_closes:
        closes = None
        try:
            closes = _date.fromisoformat(raw_closes)
        except ValueError:
            errors.append('The closing date must be a real date, as YYYY-MM-DD.')
        if closes is None:
            return opens, None
        if not opens:
            errors.append('A closing date needs an opening date to count from.')
            return opens, None
        if closes < opens:
            errors.append('The closing date cannot be before the opening date.')
            return opens, None
        return opens, (closes - opens).days + 1

    days = None
    if raw_days:
        try:
            days = int(raw_days)
        except ValueError:
            errors.append('Days open must be a whole number.')
        else:
            if days < 1:
                errors.append('Days open must be at least 1.')
                days = None
    if days and not raw_opens:
        errors.append('A length needs an opening date to count from.')
    return opens, days

@_vpsea_required
def vpsea_scholarship_add(request):
    """Add a programme to the catalogue."""
    errors = []
    if request.method == 'POST':
        p = request.POST
        name = p.get('name','').strip()
        stype = p.get('type','').strip()
        description = p.get('description','').strip()
        background = p.get('background','').strip()
        eligibility_list = [line.strip() for line
                            in p.get('eligibility_list', '').splitlines()
                            if line.strip()]
        benefits = [line.strip() for line
                    in p.get('benefits', '').splitlines() if line.strip()]
        if not name:
            errors.append('Name is required.')
        if not stype:
            errors.append('Type is required.')
        errors += _column_name_errors(p)
        if not errors:
            Scholarship.objects.create(
                name=name, type=stype, category='application',
                description=description, eligibility='',
                background=background, eligibility_list=eligibility_list,
                benefits=benefits, group=p.get('group','internal'), is_active=True,
                logo=_posted_logo(p),
                table_columns=scholar_columns.clean_choice(p.getlist('table_columns')),
                extra_columns=_posted_custom_columns(p),
            )
            return redirect('/vpsea/scholarships/?added=1')
    from .constants import available_logos
    return render(request, 'vpsea/scholarship_form.html', {
        'action': 'Add', 'errors': errors, 'form': request.POST,
        'logos': available_logos(),
        **_column_picker_context(
            request.POST if request.method == 'POST' else None,
            stype=request.POST.get('type', '') if request.method == 'POST' else ''),
    })

@_vpsea_required
def vpsea_scholarship_edit(request, pk):
    """Edit a programme."""
    try:
        s = Scholarship.objects.get(pk=pk)
    except Scholarship.DoesNotExist:
        return redirect('/vpsea/scholarships/')
    errors = []
    if request.method == 'POST':
        p = request.POST
        s.name = p.get('name','').strip()
        s.type = p.get('type','').strip()
        s.description = p.get('description','').strip()
        s.background = p.get('background','').strip()
        s.group = p.get('group', 'internal')
        s.eligibility_list = [line.strip() for line
                              in p.get('eligibility_list', '').splitlines()
                              if line.strip()]
        s.benefits = [line.strip() for line
                      in p.get('benefits', '').splitlines() if line.strip()]
        s.logo = _posted_logo(p)
        s.table_columns = scholar_columns.clean_choice(p.getlist('table_columns'))
        s.extra_columns = _posted_custom_columns(p)
        if not s.name:
            errors.append('Name is required.')
        if not s.type:
            errors.append('Type is required.')
        errors += _column_name_errors(p)
        if not errors:
            s.save()
            return redirect('/vpsea/scholarships/?saved=1')
    from .constants import available_logos
    return render(request, 'vpsea/scholarship_form.html', {
        'action': 'Edit', 'errors': errors, 's': s,
        'logos': available_logos(),
        **_column_picker_context(
            request.POST if request.method == 'POST' else None, s),
    })

@_vpsea_required
def vpsea_scholarship_toggle(request, pk):
    """Activate or retire a programme."""
    from django.db.models import Q

    if request.method == 'POST':
        Scholarship.objects.filter(pk=pk).update(is_active=Q(is_active=False))
    return redirect('/vpsea/scholarships/')

PARTNERS_BACK = '/vpsea/partners/'


def _partner_error(message):
    """Send the office back to the partner page with one message."""
    from urllib.parse import quote

    return redirect(f'{PARTNERS_BACK}?error={quote(message)}')


def _partner_saved(name):
    """Send the office back having saved a partner."""
    from urllib.parse import quote

    return redirect(f'{PARTNERS_BACK}?saved={quote(name)}')


def _create_partner_office(request):
    """Create a partner office and the account that signs into it."""
    from urllib.parse import quote

    from .models import ActivityLog, PartnerOffice

    name = (request.POST.get('name') or '').strip()
    email = (request.POST.get('email') or '').strip().lower()
    password = request.POST.get('password') or ''

    errors = []
    if not name:
        errors.append('A partner name is required.')
    if not email:
        errors.append('An email address is required — it is how they sign in.')
    if len(password) < 8:
        errors.append('The password must be at least 8 characters.')
    if name and PartnerOffice.objects.filter(name__iexact=name).exists():
        errors.append(f'A partner called {name} already exists.')
    if email and User.objects.filter(email__iexact=email).exists():
        errors.append(f'{email} already has an account.')
    if errors:
        return _partner_error(' '.join(errors))

    with transaction.atomic():
        office = PartnerOffice.objects.create(
            name=name, logo=_posted_logo(request.POST))
        office.scholarships.set(_posted_partner_scholarships(request.POST))
        account = User.objects.create_user(
            username=email, email=email, password=password,
            role='partner', first_name=name, last_name='',
        )
        account.partner_office = office
        account.save(update_fields=['partner_office'])
    ActivityLog.record(
        request.user, f'Created the partner office {name}',
        verb='create', request=request)
    return redirect(f'{PARTNERS_BACK}?created={quote(name)}')


def _set_partner_access(request, office):
    """Rename a partner and change which programmes it may read."""
    from .models import ActivityLog, PartnerOffice

    was = office.name
    posted_name = request.POST.get('name')
    name = office.name if posted_name is None else posted_name.strip()
    if not name:
        return _partner_error('A partner name is required.')
    if PartnerOffice.objects.filter(name__iexact=name).exclude(pk=office.pk).exists():
        return _partner_error(f'A partner called {name} already exists.')

    office.name = name
    office.scholarships.set(_posted_partner_scholarships(request.POST))
    office.may_add_scholarships = bool(request.POST.get('may_add_scholarships'))
    office.logo = _posted_logo(request.POST)
    office.save(update_fields=['name', 'may_add_scholarships', 'logo'])

    renamed = f' and renamed it from {was}' if was != name else ''
    ActivityLog.record(
        request.user, f'Changed what {office.name} can see{renamed}',
        verb='update', request=request)
    return _partner_saved(office.name)


def _reset_partner_password(request, office):
    """Set a new password on one of a partner's accounts."""
    from .models import ActivityLog

    account = office.accounts.filter(pk=request.POST.get('account_id')).first()
    password = request.POST.get('password') or ''
    if not account:
        return _partner_error("That account is not this partner's.")
    if len(password) < 8:
        return _partner_error('The password must be at least 8 characters.')

    account.set_password(password)
    account.save(update_fields=['password'])
    ActivityLog.record(
        request.user, f'Reset the password for {account.email} ({office.name})',
        verb='update', request=request)
    return _partner_saved(office.name)


def _delete_partner_office(request, office):
    """Remove a partner office and every account that signed into it."""
    from urllib.parse import quote

    from .models import ActivityLog

    name = office.name
    emails = list(office.accounts.values_list('email', flat=True))
    with transaction.atomic():
        office.accounts.all().delete()
        office.delete()
    ActivityLog.record(
        request.user,
        f'Deleted the partner office {name} and {len(emails)} account(s)',
        verb='delete', request=request)
    return redirect(f'{PARTNERS_BACK}?deleted={quote(name)}')


def _toggle_partner_office(request, office):
    """Suspend a partner office, or let it back in."""
    from .models import ActivityLog

    office.is_active = not office.is_active
    office.save(update_fields=['is_active'])
    state = 'Re-enabled' if office.is_active else 'Suspended'
    ActivityLog.record(
        request.user, f'{state} the partner office {office.name}',
        verb='other', request=request)
    return _partner_saved(office.name)


PARTNER_ACTIONS = {
    'access': _set_partner_access,
    'password': _reset_partner_password,
    'delete': _delete_partner_office,
    'toggle': _toggle_partner_office,
}


@_vpsea_required
def vpsea_partners(request):
    """Manage partner offices and what each may see."""
    from .constants import available_logos
    from .models import PartnerOffice

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            return _create_partner_office(request)

        office = PartnerOffice.objects.filter(
            pk=request.POST.get('office_id')).first()
        if not office:
            return _partner_error('That partner was not found.')

        handler = PARTNER_ACTIONS.get(action)
        if handler is None:
            return _partner_error('Unknown action.')
        return handler(request, office)

    return render(request, 'vpsea/partners.html', {
        'offices': (PartnerOffice.objects
                    .prefetch_related('scholarships', 'accounts')
                    .order_by('name')),
        'scholarships': Scholarship.objects.order_by('name'),
        'logos': available_logos(),
        'created': request.GET.get('created'),
        'saved': request.GET.get('saved'),
        'deleted': request.GET.get('deleted'),
        'error': request.GET.get('error'),
    })

def _posted_partner_scholarships(posted):
    """The programmes posted for a partner office."""
    return list(Scholarship.objects.filter(id__in=posted.getlist('scholarships')))
