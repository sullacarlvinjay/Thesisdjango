from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.clickjacking import xframe_options_exempt
from .models import StudentProfile, Scholarship, Application, Notification, Announcement, User, AffirmativeStaffApplication, AcademicRenewal, ScholarshipLinkRequest, TESApplication, BIPSU_SCHOOLS, BIPSU_COURSES, split_ched
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from django.core.files.base import ContentFile
from django.http import HttpResponse
from io import BytesIO


# — Landing ——————————————————————————————————

def landing_view(request):
    qs = Scholarship.objects.filter(is_active=True).order_by('type')
    return render(request, 'landing.html', {
        'scholarships': qs,
        'internal': qs.filter(group='internal'),
        'external': qs.filter(group='external'),
        'institutional': qs.filter(group='institutional'),
    })


# — Academic auth ———————————————————————————————————

PORTAL_FOR_ROLE = {
    'student': '/student/applications/',
    'nsu_staff': '/nsu-staff/',
    'vpsea': '/vpsea/',
    'unifast': '/unifast/',
    'super': '/super/',
}


def _portal_for(user):
    """Where this account lands after signing in."""
    return PORTAL_FOR_ROLE.get(user.role, '/')


def login_view(request):
    # Already signed in — including someone the middleware just released, who
    # would otherwise be staring at a login form they no longer need.
    if request.user.is_authenticated:
        return redirect(_portal_for(request.user))

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user and not user.can_sign_in:
            # Only reachable with the right password, so this tells the person
            # about their own account and nobody about anyone else's.
            return render(request, 'login.html', {
                'verification_status': user.verification_status,
                'verification_note': user.verification_note,
            })
        if user:
            login(request, user)
            return redirect(_portal_for(user))
        return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('/')


def _await_verification(request, user):
    """Hand a freshly registered account off to the SDSO, without signing it in.

    The email goes in the session rather than the URL so it is not left in
    browser history or a shared link.
    """
    from .models import ActivityLog
    ActivityLog.objects.create(
        user=user,
        action=f'Account registered — awaiting SDSO verification ({user.get_role_display()})',
    )
    from django.utils import timezone
    from .middleware import PENDING_EMAIL, PENDING_SINCE
    request.session[PENDING_EMAIL] = user.email
    request.session[PENDING_SINCE] = timezone.now().isoformat()
    return redirect('/register/received/')


def registration_received(request):
    """The waiting room. It refreshes itself, so nobody has to watch for the news.

    By the time this runs the middleware has already signed the visitor in if
    the SDSO released them, so an authenticated caller here means 'verified
    while you were waiting' — send them straight to their portal.
    """
    from .middleware import PENDING_EMAIL
    if request.user.is_authenticated:
        return redirect(_portal_for(request.user))

    email = request.session.get(PENDING_EMAIL, '')
    account = User.objects.filter(email=email).first() if email else None
    rejected = account is not None and account.verification_status == 'rejected'
    return render(request, 'registration_received.html', {
        'email': email,
        'rejected': rejected,
        'note': account.verification_note if rejected else '',
        # Only keep reloading while there is genuinely something to wait for.
        'waiting': bool(account) and account.awaiting_verification,
    })


def _register_context():
    """School and course lists for the signup form's dependent dropdowns.

    Students used to type their course free-hand, which is why courses on file
    read 'BSIT', 'Batchelor of Science in Computer Science ' and so on, and why
    their school could not be worked out from them.
    """
    import json
    return {
        'bipsu_schools': BIPSU_SCHOOLS,
        'bipsu_courses_json': json.dumps(BIPSU_COURSES),
    }


def register_view(request):
    if request.method == 'POST':
        p = request.POST
        errors = []
        account_type = p.get('account_type', 'student')

        if p.get('password') != p.get('confirm_password'):
            errors.append('Passwords do not match.')
        if User.objects.filter(email=p.get('email')).exists():
            errors.append('Email already registered.')

        if account_type == 'student':
            if not p.get('student_id'):
                errors.append('Student ID is required.')
            elif StudentProfile.objects.filter(student_id=p.get('student_id')).exists():
                errors.append('Student ID already registered.')

        if errors:
            return render(request, 'register.html', dict(_register_context(), errors=errors, post=p))

        # ── Create the Django user ──────────────────────────────────────────
        user = User.objects.create_user(
            username=p.get('email'),
            email=p.get('email'),
            password=p.get('password'),
            first_name=p.get('first_name', '').strip(),
            last_name=p.get('last_name', '').strip(),
            role=account_type,
            # Nobody signs in off the public form until the SDSO says so.
            verification_status='pending',
        )

        if account_type == 'student':
            # ── Student: create a StudentProfile ───────────────────────────
            from .constants import school_for_course
            course = p.get('course', '')
            StudentProfile.objects.create(
                user=user,
                student_id=p.get('student_id'),
                school=p.get('school', '').strip() or school_for_course(course),
                course=course,
                year_level=int(p.get('year_level', 1) or 1),
                contact_number=p.get('contact_number', ''),
                date_of_birth=p.get('date_of_birth') or None,
                gender=p.get('gender', ''),
                # Collected here because nothing else does: the masterlist
                # exports carry a MIDDLE NAME and an M.I. column, and the
                # office forms only ever set the given and family names.
                middle_name=p.get('middle_name', '').strip(),
                suffix=p.get('suffix', '').strip(),
            )
            return _await_verification(request, user)

        else:
            # ── BiPSU Staff: the employment details go on the StaffProfile,
            #    which is the employee's own record. A Draft application is
            #    created alongside it so the apply page has something to
            #    continue from.
            from .models import AffirmativeStaffApplication, StaffProfile
            StaffProfile.objects.create(
                user=user,
                middle_name=p.get('middle_name', '').strip(),
                suffix=p.get('suffix', '').strip(),
                contact_number=p.get('contact_number', '').strip(),
                date_of_birth=p.get('date_of_birth') or None,
                gender=p.get('gender', ''),
                employee_id=p.get('school_id', '').strip(),
                department=p.get('department', '').strip(),
                position=p.get('position', '').strip(),
            )
            full_name = f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip()
            AffirmativeStaffApplication.objects.create(
                full_name=full_name,
                email=user.email,
                contact_number=p.get('contact_number', '').strip(),
                date_of_birth=p.get('date_of_birth') or '2000-01-01',
                gender=p.get('gender', ''),
                course=p.get('course', ''),
                year_level=int(p.get('year_level', 1) or 1),
                student_id=p.get('school_id', '').strip(),
                department=p.get('department', '').strip(),
                position=p.get('position', '').strip(),
                is_nsu_staff=True,
                qualified_for='Staff',
                status='Draft',
            )
            from .models import ActivityLog
            ActivityLog.objects.create(
                user=user,
                action=(
                    f"Staff account created — "
                    f"School ID: {p.get('school_id','—')} | "
                    f"Department: {p.get('department','—')} | "
                    f"Position: {p.get('position','—')} | "
                    f"Contact: {p.get('contact_number','—')}"
                ),
            )
            return _await_verification(request, user)

    return render(request, 'register.html', dict(_register_context(), post={}))


# — Academic student pages ——————————————————————————

def _tristate(raw, current):
    """('yes' | 'no' | '') -> (True | False | None), keeping the current value on junk.

    A checkbox cannot express these fields. It only ever posts on or off, so an
    untouched box would record a confident "no" for a question nobody asked —
    and the TES recommender's whole design turns on telling 'confirmed no' apart
    from 'not yet collected'. Hence a three-option select, and hence this.
    """
    value = (raw or '').strip().casefold()
    if value == 'yes':
        return True
    if value == 'no':
        return False
    if value == 'unknown':
        return None
    return current


def _positive_int(raw, current):
    """A whole number above zero, or the value already on file."""
    text = (raw or '').strip()
    if text == '':
        return None
    if text.isdigit() and int(text) > 0:
        return int(text)
    return current


def _parse_gwa(raw):
    """A GWA out of a form field, or None when it is blank or not a number.

    Anything outside the 1.00–5.00 Philippine grading range is treated as not
    entered rather than saved — a stray keystroke should not overwrite a real
    grade on the profile.
    """
    try:
        value = float((raw or '').strip())
    except (TypeError, ValueError):
        return None
    return value if 1.0 <= value <= 5.0 else None


def _is_enrolled(profile):
    """True only when the student has an APPROVED application or approved linked scholarship.
    Pending/Needs Revision applications do not count as enrolled — the student
    should still be able to see their other apply options while waiting for a decision.

    An approved link only counts for the semester it was granted for, so a link
    from a past semester does not keep blocking this semester's applications.
    """
    if not profile:
        return False
    if Application.objects.filter(student=profile, status='Approved').exists():
        return True
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return ScholarshipLinkRequest.objects.filter(
        student=profile, status='Approved', term_label=settings_obj.academic_year,
    ).exists()


def _validate_proof(uploaded, settings_obj):
    """Server-side check for an uploaded proof document.

    The template's accept="..." attribute is advisory only — anything can be
    POSTed — so the extension and size are enforced here.
    """
    if not uploaded:
        return ['Proof document is required.']
    import os
    errors = []
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in ('.pdf', '.jpg', '.jpeg', '.png'):
        errors.append(f'Unsupported file type "{ext or uploaded.name}". Upload a PDF, JPG or PNG.')
    max_mb = settings_obj.max_file_size_mb or 5
    if uploaded.size > max_mb * 1024 * 1024:
        errors.append(f'File is too large ({uploaded.size / 1048576:.1f} MB). Maximum is {max_mb} MB.')
    return errors


@login_required(login_url='/login/')
def student_dashboard(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    scholarships = Scholarship.objects.filter(is_active=True)
    matched = []
    for s in scholarships:
        score = s.match_score(profile)
        matched.append({'name': s.name, 'description': s.description, 'match': score})
    matched.sort(key=lambda x: x['match'], reverse=True)
    applications = Application.objects.filter(student=profile) if profile else Application.objects.none()
    announcements = Announcement.objects.order_by('-created_at')[:3]
    top_match = matched[0]['match'] if matched else 0
    top_match_offset = round(314 * (1 - top_match / 100))
    timeline = [
        {'date': a.submitted_at, 'title': f"{a.scholarship.name} — {a.status}", 'status': 'done' if a.status == 'Approved' else 'pending'}
        for a in applications.select_related('scholarship').order_by('-submitted_at')[:5]
    ]
    ctx = {
        'profile': profile,
        'enrolled': _is_enrolled(profile),
        'scholarships': matched,
        'announcements': announcements,
        'top_match': top_match,
        'top_match_offset': top_match_offset,
        'timeline': timeline,
        'dashboard': {
            'recommended_count': len([s for s in matched if s['match'] >= 50]),
            'pending_count': applications.filter(status='Pending Validation').count(),
            'approved_count': applications.filter(status='Approved').count(),
            'notification_count': Notification.objects.filter(student=profile, is_read=False).count() if profile else 0,
        },
    }
    return render(request, 'student/dashboard.html', ctx)


@login_required(login_url='/login/')
def student_apply_academic(request):
    from .models import ApplicationDocument
    profile = StudentProfile.objects.filter(user=request.user).first()
    # Block if already has an active (non-rejected, non-draft) application for any scholarship
    existing = Application.objects.filter(
        student=profile, status__in=['Pending Validation', 'Approved', 'Needs Revision']
    ).select_related('scholarship').first() if profile else None
    if not existing:
        # Also block if student has an approved linked scholarship
        existing_link = ScholarshipLinkRequest.objects.filter(
            student=profile, status='Approved'
        ).first() if profile else None
        if existing_link:
            return render(request, 'student/apply_academic.html', {
                'profile': profile, 'blocked': True,
                'blocked_reason': f'You are already enrolled in the {existing_link.scholarship_type} scholarship program. You cannot apply to another scholarship while enrolled in a program.',
                'classification': '', 'eligible': False,
            })
    if existing:
        return render(request, 'student/apply_academic.html', {
            'profile': profile, 'blocked': True,
            'blocked_reason': f'You already have an active {existing.scholarship.name} application ({existing.status}). You cannot apply to another scholarship while enrolled in a program.',
            'classification': '', 'eligible': False,
        })
    if request.method == 'POST':
        scholarship = Scholarship.objects.filter(type='Academic').first()
        if scholarship and profile:
            # The GWA the student declares here is the one the whole application
            # is judged on, so it belongs on the profile — the ranking page,
            # reports and the office's own screens all read it from there. It
            # used to be written only into form_data, which left the profile on
            # its 0.0 default and every self-registered student unrankable.
            # The uploaded Certificate of Grades is what the office checks it
            # against.
            declared = _parse_gwa(request.POST.get('gwa'))
            if declared is not None:
                profile.gwa = declared
                profile.save(update_fields=['gwa'])
            app = Application.objects.create(
                student=profile, scholarship=scholarship,
                status='Pending Validation',
                form_data=request.POST.dict()
            )
            for field, label in [
                ('doc_certificate_of_grades', 'Certificate Of Grades'),
                ('doc_certificate_of_enrollment', 'Certificate Of Enrollment'),
                ('doc_prospectus', 'Prospectus'),
                ('doc_id_photo', 'Id Photo'),
                ('doc_application_form', 'Application Form'),
            ]:
                uploaded = request.FILES.get(field)
                if uploaded:
                    ApplicationDocument.objects.create(application=app, name=label, file=uploaded)
        return redirect('/student/applications/')
    from .constants import (
        COLLEGE_SCHOLAR_MAX_GWA, UNIVERSITY_SCHOLAR_MAX_GWA, academic_classification,
    )
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    gwa = profile.gwa if profile else 0
    classification = academic_classification(gwa)
    # The term is the office's, not the applicant's. The form used to hard-code
    # '2024-2025' and '2nd Semester' into the markup, so every application ever
    # submitted claimed a term two years stale — and then failed to match the
    # office's own semester filter.
    term = SystemSettings.parse_label(settings_obj.academic_year)
    return render(request, 'student/apply_academic.html', {
        'profile': profile,
        'active_school_year': term['sy'],
        'active_semester': term['semester'],
        'classification': classification,
        'eligible': classification in ('University Scholar', 'College Scholar'),
        'enrolled': _is_enrolled(profile),
        # The page re-runs the same rule live as the applicant types, off these
        # numbers, so what it shows and what the view decides cannot disagree.
        'university_max_gwa': UNIVERSITY_SCHOLAR_MAX_GWA,
        'college_max_gwa': COLLEGE_SCHOLAR_MAX_GWA,
    })
    


@login_required(login_url='/login/')
def student_applications(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    applications = Application.objects.filter(student=profile).select_related('scholarship') if profile else Application.objects.none()
    tes_applications = TESApplication.objects.filter(student=profile) if profile else TESApplication.objects.none()
    return render(request, 'student/applications.html', {
        'applications': applications,
        'tes_applications': tes_applications,
        'enrolled': _is_enrolled(profile),
    })


@login_required(login_url='/login/')
def student_notifications(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    notifications = Notification.objects.filter(student=profile).order_by('-created_at') if profile else Notification.objects.none()
    return render(request, 'student/notifications.html', {'notifications': notifications, 'enrolled': _is_enrolled(profile)})


@login_required(login_url='/login/')
def student_renewal_academic(request):
    from .models import SystemSettings
    profile = StudentProfile.objects.filter(user=request.user).first()
    has_academic = Application.objects.filter(student=profile, scholarship__type='Academic', status='Approved').exists() if profile else False
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    if request.method == 'POST' and profile:
        cog = request.FILES.get('certificate_of_grades')
        coe = request.FILES.get('certificate_of_enrollment')
        errors = []
        if not cog:
            errors.append('Certificate of Grades is required.')
        if not coe:
            errors.append('Certificate of Enrollment is required.')
        if errors:
            renewals = AcademicRenewal.objects.filter(student=profile).order_by('-submitted_at')
            return render(request, 'student/renewal_academic.html', {
                'profile': profile, 'has_academic': has_academic,
                'renewals': renewals, 'errors': errors,
                'semester': settings_obj.active_semester, 'academic_year': settings_obj.academic_year,
                'enrolled': _is_enrolled(profile),
            })
        AcademicRenewal.objects.create(student=profile, certificate_of_grades=cog, certificate_of_enrollment=coe)
        return redirect('/student/renewal/academic/?submitted=1')
    renewals = AcademicRenewal.objects.filter(student=profile).order_by('-submitted_at') if profile else []
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    return render(request, 'student/renewal_academic.html', {
        'profile': profile, 'has_academic': has_academic,
        'renewals': renewals, 'submitted': request.GET.get('submitted'),
        'semester': parsed['semester'], 'academic_year': parsed['sy'],
        'enrolled': _is_enrolled(profile),
    })


@login_required(login_url='/login/')
@login_required(login_url='/login/')
def student_profile(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    errors = []
    saved = False
    if request.method == 'POST' and profile:
        p = request.POST
        u = profile.user
        u.save()
        # The given and family names are the office's to set, but nothing in the
        # system ever collected the middle name — which the masterlist exports
        # carry as their own MIDDLE NAME and M.I. columns — so the student
        # enters it here. Locked once filled, like the address below.
        if not profile.middle_name:
            profile.middle_name = p.get('middle_name', '').strip()
        profile.suffix = p.get('suffix', profile.suffix).strip()
        # Civil status, educational background and family background are all
        # locked once set, like the address below. They are what the masterlist
        # and the TES form are built from, so a later edit would silently change
        # a record the office has already reviewed. The archives edit screen is
        # the office's override when one of them was entered wrong.
        if not profile.civil_status:
            profile.civil_status = p.get('civil_status', profile.civil_status)
        profile.family_income = float(p.get('family_income', profile.family_income) or profile.family_income)
        profile.indigenous_group = p.get('indigenous_group', profile.indigenous_group)
        profile.is_pwd = 'is_pwd' in p
        profile.is_athlete = 'is_athlete' in p
        profile.is_coconut_farmer_family = 'is_coconut_farmer_family' in p
        profile.has_other_scholarship = 'has_other_scholarship' in p
        if not (profile.elementary and profile.highschool and profile.last_school):
            profile.elementary = p.get('elementary', profile.elementary)
            profile.highschool = p.get('highschool', profile.highschool)
            profile.last_school = p.get('last_school', profile.last_school)
        # Parent names in parts — the shape CHED's TES form needs, collected
        # once here so the TES application can fill itself in from the profile.
        if not (profile.father_last_name and profile.father_first_name
                and profile.mother_last_name and profile.mother_first_name):
            for parent in ('father', 'mother'):
                for part in ('last_name', 'first_name', 'middle_name'):
                    field = f'{parent}_{part}'
                    setattr(profile, field, p.get(field, getattr(profile, field)).strip())
            profile.father_occupation = p.get('father_occupation', profile.father_occupation)
            profile.mother_occupation = p.get('mother_occupation', profile.mother_occupation)
        # TES eligibility. Each of these answers one rule in api/tes_ranking.py;
        # left unanswered they stay unknown, and the recommender reports the
        # requirement as Needs Verification rather than failing the student.
        profile.citizenship = p.get('citizenship', profile.citizenship)
        profile.household_size = _positive_int(p.get('household_size'), profile.household_size)
        profile.year_first_enrolled = _positive_int(
            p.get('year_first_enrolled'), profile.year_first_enrolled)
        profile.is_listahanan_household = _tristate(
            p.get('is_listahanan_household'), profile.is_listahanan_household)
        profile.is_4ps_beneficiary = _tristate(
            p.get('is_4ps_beneficiary'), profile.is_4ps_beneficiary)
        profile.has_previous_degree = _tristate(
            p.get('has_previous_degree'), profile.has_previous_degree)
        # Affirmative eligibility
        raw_shs = p.get('shs_gpa', '').strip()
        if raw_shs:
            try: profile.shs_gpa = float(raw_shs)
            except ValueError: pass
        raw_suc = p.get('suc_exam_score', '').strip()
        if raw_suc:
            try: profile.suc_exam_score = float(raw_suc)
            except ValueError: pass
        profile.is_tes_beneficiary = 'is_tes_beneficiary' in p
        if request.FILES.get('shs_gpa_cert'):
            profile.shs_gpa_cert = request.FILES['shs_gpa_cert']
        if request.FILES.get('suc_exam_cert'):
            profile.suc_exam_cert = request.FILES['suc_exam_cert']
        # Address: only update if not yet locked (all three empty)
        if not (profile.barangay and profile.municipality and profile.province):
            profile.barangay = p.get('barangay', profile.barangay)
            profile.municipality = p.get('municipality', profile.municipality)
            profile.province = p.get('province', profile.province)
        profile.save()
        saved = True
    import json
    from .constants import CIVIL_STATUSES
    address_locked = bool(profile and profile.barangay and profile.municipality and profile.province)
    # A group locks only once it is complete, so a half-filled one stays open.
    civil_status_locked = bool(profile and profile.civil_status)
    education_locked = bool(
        profile and profile.elementary and profile.highschool and profile.last_school)
    family_locked = bool(
        profile and profile.father_last_name and profile.father_first_name
        and profile.mother_last_name and profile.mother_first_name)
    return render(request, 'student/profile.html', {
        'profile': profile, 'errors': errors, 'saved': saved,
        'enrolled': _is_enrolled(profile),
        'bipsu_schools': BIPSU_SCHOOLS,
        'bipsu_courses_json': json.dumps(BIPSU_COURSES),
        'address_locked': address_locked,
        'middle_name_locked': bool(profile and profile.middle_name),
        'civil_status_locked': civil_status_locked,
        'education_locked': education_locked,
        'family_locked': family_locked,
        'civil_statuses': CIVIL_STATUSES,
    })


@login_required(login_url='/login/')
def student_link_scholarship(request):
    from .models import SystemSettings, CHED_TIER_CHOICES, SCHOLARSHIP_TYPE_CHOICES
    profile = StudentProfile.objects.filter(user=request.user).first()
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    parsed = SystemSettings.parse_label(active_label)

    link_requests = list(
        ScholarshipLinkRequest.objects.filter(student=profile)
        .select_related('reviewed_by', 'matched_archive')
        .order_by('-submitted_at')
    ) if profile else []

    approved = next((r for r in link_requests if r.status == 'Approved'), None)
    pending = next((r for r in link_requests if r.status == 'Pending'), None)

    # There is nothing to link if the student is already in a program, and a
    # pending request has to be decided before another one is worth filing.
    if not profile:
        blocked_reason = 'Your student profile is not set up yet. Fill in My Profile first.'
    elif approved:
        blocked_reason = f'Your {approved.get_scholarship_type_display()} is already linked to this account.'
    elif Application.objects.filter(student=profile, status='Approved').exists():
        blocked_reason = 'You already have an approved scholarship on this account — there is nothing to link.'
    elif pending:
        blocked_reason = (
            f'You already have a pending link request for {pending.get_scholarship_type_display()}. '
            'Please wait for the VPSEA office to review it.'
        )
    else:
        blocked_reason = ''

    def ctx(**extra):
        return {
            'profile': profile,
            'scholarship_types': SCHOLARSHIP_TYPE_CHOICES,
            'ched_tiers': CHED_TIER_CHOICES,
            'link_requests': link_requests,
            'enrolled': _is_enrolled(profile),
            'blocked_reason': blocked_reason,
            'academic_year': parsed['sy'],
            'semester': parsed['semester'],
            'max_upload_mb': settings_obj.max_file_size_mb or 5,
            **extra,
        }

    if request.method == 'POST':
        if blocked_reason:
            return render(request, 'student/link_scholarship.html', ctx(errors=[blocked_reason]))
        stype = request.POST.get('scholarship_type', '')
        notes = request.POST.get('notes', '')
        award_number = request.POST.get('award_number', '').strip()
        proof = request.FILES.get('proof_document')
        # CHED is awarded at two tiers under a single programme and every
        # masterlist reports the two in separate blocks, so the student has to
        # say which one they hold. Other programmes have one tier; blank there.
        tier = request.POST.get('award_tier', '') if stype == 'CHED' else ''
        errors = []
        if stype not in [t for t, _ in SCHOLARSHIP_TYPE_CHOICES]:
            errors.append('Please select a scholarship type.')
        elif stype == 'CHED' and tier not in [t for t, _ in CHED_TIER_CHOICES]:
            errors.append('Please choose whether your CHED award is Full Merit / Full Scholar '
                          'or Half Merit / Partial Scholar — your award letter says which.')
        errors += _validate_proof(proof, settings_obj)
        if errors:
            return render(request, 'student/link_scholarship.html', ctx(errors=errors, post=request.POST))
        ScholarshipLinkRequest.objects.create(
            student=profile, scholarship_type=stype, proof_document=proof,
            notes=notes, award_number=award_number, award_tier=tier,
            term_label=active_label,
        )
        return redirect('/student/link-scholarship/?submitted=1')

    return render(request, 'student/link_scholarship.html',
                  ctx(submitted=request.GET.get('submitted')))


# — UniFAST portal pages ———————————————————————————

# Scholarship types the UniFAST office administers. Their portal is scoped to
# these everywhere — archives, analytics and reports alike.
UNIFAST_TYPES = ['TDP', 'TES']

# Programmes the VPSEA office must not review. TES applications are decided by
# UniFAST at /unifast/tes-applications/; VPSEA neither lists nor acts on them.
VPSEA_EXCLUDED_TYPES = ['TES']


def _unifast_required(view_fn):
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'unifast':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper


@_unifast_required
def unifast_dashboard(request):
    """Everything the UniFAST office acts on, for the active semester.

    Every figure is derived from records in the system — the office reviews TES
    applications here and imports TDP/TES lists, so there is no need to invent
    billing percentages.
    """
    from .models import (Announcement, ImportedScholar, ActivityLog, SystemSettings,
                         TESApplication)
    from . import tes_report

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    label = settings_obj.academic_year
    parsed = SystemSettings.parse_label(label)

    tes = TESApplication.objects.all()
    tes_pending = tes.filter(status='Pending')
    tes_approved = tes.filter(status='Approved').count()
    tes_rejected = tes.filter(status='Rejected').count()
    tdp_scholars = Application.objects.filter(
        status='Approved', scholarship__type='TDP').count()

    reviewed = tes_approved + tes_rejected
    approval_rate = round(tes_approved * 100 / reviewed) if reviewed else 0

    # Imported rows still waiting to be claimed by a student account.
    imported = {
        stype: ImportedScholar.objects.filter(
            scholarship_type=stype, term_label=label, claimed_by__isnull=True,
        ).count()
        for stype in UNIFAST_TYPES
    }

    programs = [
        {'label': 'TES', 'count': tes_approved, 'color': '#3b5bdb',
         'href': '/unifast/tes-applications/'},
        {'label': 'TDP', 'count': tdp_scholars, 'color': '#1971c2',
         'href': '/unifast/archives/?type=TDP'},
    ]
    biggest = max((p['count'] for p in programs), default=0) or 1
    for p in programs:
        p['width'] = round(p['count'] * 100 / biggest)

    return render(request, 'unifast/dashboard.html', {
        'academic_year': parsed['sy'],
        'semester': parsed['semester'],
        'tes_total': tes.count(),
        'tes_pending_count': tes_pending.count(),
        'tes_beneficiaries': tes_approved,
        'tes_rejected': tes_rejected,
        'approval_rate': approval_rate,
        'tdp_scholars': tdp_scholars,
        'total_scholars': tes_approved + tdp_scholars,
        # No billing figure is derived here. It was grantees x a flat rate, which
        # is not something this office decides, and no template rendered it.
        'programs': programs,
        'imported': imported,
        'imported_total': sum(imported.values()),
        'pending_queue': list(
            tes_pending.select_related('student__user').order_by('submitted_at')[:6]
        ),
        'announcements': list(
            Announcement.objects.filter(published_by=request.user)
            .order_by('-created_at')[:3]
        ),
        'recent_activity': list(
            ActivityLog.objects.filter(user=request.user)
            .order_by('-created_at')[:5]
        ),
    })



# — VPSEA portal pages ———————————————————————————————————

def _vpsea_required(view_fn):
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'vpsea':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper


@_vpsea_required
def vpsea_affirmative_applications(request):
    from .models import AffirmativeStaffApplication, Application
    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        tab = request.POST.get('tab', 'affirmative')
        if tab == 'academic':
            try:
                # excluded types are UniFAST's to decide, so a posted id for one
                # finds nothing here rather than being approved by this office.
                acad_app = (
                    Application.objects.select_related('student')
                    .exclude(scholarship__type__in=VPSEA_EXCLUDED_TYPES)
                    .get(id=app_id)
                )
                acad_app.status = new_status
                acad_app.remarks = remarks
                acad_app.save()
            except Application.DoesNotExist:
                pass
            return redirect(f'/vpsea/affirmative/?tab=academic')
        else:
            try:
                aff_app = AffirmativeStaffApplication.objects.get(id=app_id)
                aff_app.status = new_status
                aff_app.remarks = remarks
                aff_app.save()
                # On approval: create Django User + StudentProfile + Application
                if new_status == 'Approved' and not User.objects.filter(email=aff_app.email).exists():
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
            except AffirmativeStaffApplication.DoesNotExist:
                pass
            return redirect(f'/vpsea/affirmative/?tab={tab}')

    tab = request.GET.get('tab', 'academic')
    academic_apps = (
        Application.objects
        .select_related('student__user', 'scholarship')
        .prefetch_related('documents')
        .exclude(scholarship__type__in=['Staff'])
        .exclude(scholarship__type__in=VPSEA_EXCLUDED_TYPES)
        .order_by('-submitted_at')
    )
    affirmative_apps = AffirmativeStaffApplication.objects.filter(qualified_for='Affirmative').order_by('-submitted_at')
    staff_apps = AffirmativeStaffApplication.objects.filter(qualified_for='Staff').order_by('-submitted_at')
    return render(request, 'vpsea/affirmative.html', {
        'academic_apps': academic_apps,
        'affirmative_apps': affirmative_apps,
        'staff_apps': staff_apps,
        'active_tab': tab,
    })


@_vpsea_required
def vpsea_dashboard(request):
    from .models import Application, AcademicRenewal, AffirmativeStaffApplication, SystemSettings
    from django.db.models import Q
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    active_semester = parsed['semester']
    # One indexed column, set on every row. The filter this replaces read
    # form_data['academic_year'], a key the student apply form never wrote —
    # it wrote 'school_year' — so every student-submitted application was
    # silently missing from these counts.
    apps = Application.objects.filter(term_label=settings_obj.academic_year)
    ctx = {
        'total_applicants': apps.count(),
        'approved': apps.filter(status='Approved').count(),
        'rejected': apps.filter(status='Rejected').count(),
        'pending': apps.filter(status='Pending Validation').count(),
        'renewals': AcademicRenewal.objects.filter(status='Pending').count(),
        'pending_staff': AffirmativeStaffApplication.objects.filter(qualified_for='Staff', status='Pending Validation').count(),
        'pending_affirmative': AffirmativeStaffApplication.objects.filter(qualified_for='Affirmative', status='Pending Validation').count(),
        'active_sy_display': f"{active_sy} — {active_semester}",
    }
    return render(request, 'vpsea/dashboard.html', ctx)


@_vpsea_required
def vpsea_renewals(request):
    if request.method == 'POST':
        from .models import SystemSettings
        from django.utils import timezone
        renewal_id = request.POST.get('renewal_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        AcademicRenewal.objects.filter(id=renewal_id).update(status=new_status, remarks=remarks)
        # On approval: create a new Application for the current semester so the
        # student appears in the current-SY archives.
        if new_status == 'Approved':
            try:
                renewal = AcademicRenewal.objects.select_related('student').get(id=renewal_id)
                scholarship = Scholarship.objects.filter(type='Academic').first()
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
    renewals = AcademicRenewal.objects.select_related('student__user').order_by('-submitted_at')
    return render(request, 'vpsea/renewals.html', {
        'renewals': renewals,
        'approved_count': renewals.filter(status='Approved').count(),
        'pending_count': renewals.filter(status='Pending').count(),
    })


def _archive_candidates(req, label=None):
    """Imported archive rows that could be the scholar behind a link request.

    Matched on student number, award number or exact first+last name. Rows that
    another student already claimed are never offered again.
    """
    from .models import ImportedScholar
    from django.db.models import Q

    profile = req.student
    qs = ImportedScholar.objects.filter(
        scholarship_type=req.scholarship_type, claimed_by__isnull=True,
    )
    if label is not None:
        qs = qs.filter(term_label=label)

    cond = Q()
    if profile.student_id:
        cond |= Q(student_id__iexact=profile.student_id)
    if req.award_number:
        cond |= Q(award_number__iexact=req.award_number)
    last = (profile.user.last_name or '').strip()
    first = (profile.user.first_name or '').strip()
    if last and first:
        cond |= Q(last_name__iexact=last, first_name__iexact=first)
    if not cond:
        return qs.none()
    return qs.filter(cond).order_by('last_name', 'first_name')


@_vpsea_required
def vpsea_link_requests(request):
    """Review queue for students linking a scholarship they already hold.

    Approving a request is what actually merges the office's imported data with
    the student's account: it creates the Approved Application for the active
    semester — so the scholar flows into archives, reports, ranking and renewals
    like any other — and marks the matched imported row as claimed so the same
    person is not counted twice.
    """
    from .models import (ScholarshipLinkRequest, ImportedScholar, SystemSettings,
                         Notification, ActivityLog, CHED_TIER_CHOICES)
    from django.utils import timezone

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    parsed = SystemSettings.parse_label(active_label)

    if request.method == 'POST':
        req = ScholarshipLinkRequest.objects.select_related('student__user').filter(
            id=request.POST.get('request_id')
        ).first()
        if not req:
            return redirect('/vpsea/link-requests/?error=Request+not+found')
        if req.status != 'Pending':
            return redirect('/vpsea/link-requests/?error=That+request+was+already+reviewed')

        action = request.POST.get('action')
        remarks = request.POST.get('remarks', '').strip()
        profile = req.student
        label = req.get_scholarship_type_display()

        if action == 'reject':
            if not remarks:
                return redirect('/vpsea/link-requests/?error=A+reason+is+required+when+rejecting')
            req.status = 'Rejected'
            req.remarks = remarks
            req.reviewed_by = request.user
            req.reviewed_at = timezone.now()
            req.save()
            Notification.objects.create(
                student=profile, type='warning',
                title=f'{label} link request rejected',
                body=f'The VPSEA office could not verify your {label} link request. Reason: {remarks}',
            )
            ActivityLog.objects.create(
                user=request.user,
                action=f'Rejected {label} link request for {profile.student_id}',
            )
            return redirect('/vpsea/link-requests/?reviewed=Rejected')

        if action != 'approve':
            return redirect('/vpsea/link-requests/')

        scholarship = Scholarship.objects.filter(type=req.scholarship_type).first()
        if not scholarship:
            return redirect(
                f'/vpsea/link-requests/?error=No+{req.scholarship_type}+program+is+configured+under+Scholarship+Programs'
            )

        # Optional: the imported archive row this student turned out to be.
        archive = None
        archive_id = request.POST.get('archive_id', '').strip()
        if archive_id:
            archive = ImportedScholar.objects.filter(
                id=archive_id, scholarship_type=req.scholarship_type,
                term_label=active_label, claimed_by__isnull=True,
            ).first()
            if not archive:
                return redirect('/vpsea/link-requests/?error=That+archive+row+is+no+longer+available')

        # The link request behind this award is reachable in reverse through
        # ScholarshipLinkRequest.linked_application, so it is not copied here.
        award_fields = {
            'source': 'link',
            'school_year': parsed['sy'],
            'semester': parsed['semester'],
            'award_number': req.award_number or (archive.award_number if archive else ''),
            'congress_district': archive.congress_district if archive else '',
            'claimed_archive': archive,
        }
        form_data = {'imported_from': archive.imported_from} if archive else {}

        # The reviewer can correct the tier the student picked — the proof
        # document is in front of them and the student is not always sure which
        # one they were awarded. It rides on the award as 'scholar_type', which
        # is the key every CHED masterlist splits its two blocks by.
        if req.scholarship_type == 'CHED':
            tier = request.POST.get('award_tier', '') or req.award_tier
            if tier not in [t for t, _ in CHED_TIER_CHOICES]:
                return redirect('/vpsea/link-requests/?error=Choose+Full+or+Half+Merit+before+approving+a+CHED+link')
            req.award_tier = tier          # persisted by the req.save() below
            form_data['scholar_type'] = dict(CHED_TIER_CHOICES)[tier]

        # Reuse this semester's row if one already exists so re-approval after a
        # correction does not leave the scholar counted twice.
        app = Application.objects.filter(
            student=profile, scholarship=scholarship,
            school_year=parsed['sy'], semester=parsed['semester'],
        ).first()
        if app:
            app.status = 'Approved'
            app.remarks = remarks
            for field, value in award_fields.items():
                setattr(app, field, value)
            app.form_data = {**app.form_data, **form_data}
            app.save()
        else:
            app = Application.objects.create(
                student=profile, scholarship=scholarship,
                status='Approved', remarks=remarks, form_data=form_data,
                **award_fields,
            )

        if archive:
            archive.claimed_by = profile
            archive.save(update_fields=['claimed_by'])
            # Carry over what the office already knows, without overwriting
            # anything the student has filled in themselves.
            changed = []
            for field, value in (
                ('course', archive.course), ('barangay', archive.barangay),
                ('municipality', archive.municipality), ('province', archive.province),
                ('gender', archive.gender),
            ):
                if value and not getattr(profile, field):
                    setattr(profile, field, value)
                    changed.append(field)
            if archive.gwa and not profile.gwa:
                profile.gwa = archive.gwa
                changed.append('gwa')
            if archive.year_level and profile.year_level in (0, 1):
                profile.year_level = archive.year_level
                changed.append('year_level')
            if changed:
                profile.save(update_fields=changed)

        req.status = 'Approved'
        req.remarks = remarks
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.matched_archive = archive
        req.linked_application = app
        req.save()

        Notification.objects.create(
            student=profile, type='success',
            title=f'{label} linked to your account',
            body=(f'Your {label} has been verified and linked for '
                  f"{parsed['sy']} {parsed['semester']}. It now appears under My Applications."),
        )
        ActivityLog.objects.create(
            user=request.user,
            action=(f'Approved {label} link request for {profile.student_id}'
                    + (f' (merged imported row #{archive.id})' if archive else ' (no imported row matched)')),
        )
        return redirect('/vpsea/link-requests/?reviewed=Approved')

    status_filter = request.GET.get('status', 'Pending')
    all_requests = ScholarshipLinkRequest.objects.select_related(
        'student__user', 'reviewed_by', 'matched_archive'
    ).order_by('-submitted_at')
    shown = all_requests.filter(status=status_filter) if status_filter in (
        'Pending', 'Approved', 'Rejected') else all_requests

    rows = []
    for req in shown:
        pending = req.status == 'Pending'
        rows.append({
            'req': req,
            # Rows the admin can merge: current semester only, so approving a
            # link never rewrites a past semester's archive.
            'candidates': list(_archive_candidates(req, active_label)) if pending else [],
            # Same scholar in earlier imports — shown as verification evidence
            # only, never claimed.
            'other_semesters': list(
                _archive_candidates(req).exclude(term_label=active_label)[:5]
            ) if pending else [],
        })

    return render(request, 'vpsea/link_requests.html', {
        'rows': rows,
        'ched_tiers': CHED_TIER_CHOICES,
        'status_filter': status_filter,
        'total_count': all_requests.count(),
        'pending_count': all_requests.filter(status='Pending').count(),
        'approved_count': all_requests.filter(status='Approved').count(),
        'rejected_count': all_requests.filter(status='Rejected').count(),
        'active_sy': parsed['sy'],
        'active_semester': parsed['semester'],
        'active_label': active_label,
        'error': request.GET.get('error'),
        'reviewed': request.GET.get('reviewed'),
    })


# The archives page answers "who holds scholarship X this term" one tab per
# programme, so a student holding nothing appears on no tab at all. This is the
# tab for the office's other question: who has the system not served.
UNAWARDED_TAB = 'No Scholarship'


def _unawarded_rows(term_label):
    """Students with no Approved award for ``term_label``, with why attached.

    "No scholarship" is not one state. A student who never applied needs an
    invitation; one waiting on review needs the queue cleared; one rejected
    needs a reason. The office can only act on the difference, so each row
    carries the student's most recent application — if they have one at all.
    """
    from .constants import academic_classification

    awarded = Application.objects.filter(
        status='Approved', term_label=term_label,
    ).values_list('student_id', flat=True)

    students = (
        StudentProfile.objects
        .exclude(id__in=awarded)
        .select_related('user')
        .prefetch_related('applications__scholarship')
        .order_by('user__last_name', 'user__first_name')
    )

    rows = []
    for profile in students:
        # Already prefetched, so this sorts in memory rather than re-querying.
        # submitted_at is a DateField, so two applications sent on the same day
        # tie on it; pk breaks the tie, otherwise a student who re-applied after
        # a rejection would still show as rejected.
        apps = sorted(profile.applications.all(),
                      key=lambda a: (a.submitted_at or date.min, a.pk),
                      reverse=True)
        latest = apps[0] if apps else None
        if latest is None:
            state = 'never'
        elif latest.status == 'Rejected':
            state = 'rejected'
        elif latest.status == 'Draft':
            state = 'draft'
        else:
            state = 'pending'
        rows.append({
            'profile': profile,
            'latest': latest,
            'state': state,
            'classification': academic_classification(profile.gwa),
        })
    return rows


@_vpsea_required
def vpsea_archives(request):
    from .models import Application, AffirmativeStaffApplication, ScholarListImport, SystemSettings, AcademicRenewal, ActivityLog
    stype = request.GET.get('type', 'Academic')
    # Build archive_types dynamically from DB so newly added scholarship types appear
    base_types = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    db_types = list(Scholarship.objects.values_list('type', flat=True).distinct())
    archive_types = base_types + [t for t in db_types if t not in base_types] + [UNAWARDED_TAB]
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year  # e.g. '26-1'
    parsed = SystemSettings.parse_label(active_label)
    active_sy = parsed['sy']           # '2025-2026'
    active_semester = parsed['semester']  # '1st Semester'

    history = ScholarListImport.objects.filter(scholarship_type=stype).order_by('-created_at')
    all_labels = list(
    ScholarListImport.objects.filter(scholarship_type=stype)
    .values_list('term_label', flat=True).distinct().order_by('-term_label')
)
    if active_label not in all_labels:
        all_labels.insert(0, active_label)
    selected_label = request.GET.get('sy', active_label)
    if selected_label not in all_labels:
        selected_label = active_label

    selected_parsed = SystemSettings.parse_label(selected_label)
    selected_sy = selected_parsed['sy']   # e.g. '2025-2026'
    sy_start = selected_parsed['sy_start']
    sy_end = selected_parsed['sy_end']

    next_label = settings_obj.next_label()
    # Human-readable label for display: '2025-2026 — 1st Semester'
    active_display = f"{active_sy} — {active_semester}"
    # Build (label, display) pairs for the SY dropdown
    all_sy_display = []
    for lbl in all_labels:
        p = SystemSettings.parse_label(lbl)
        all_sy_display.append((lbl, f"{p['sy']} — {p['semester']}"))

    # Previous label = one step back from active
    yy, s = active_label.split('-')
    if s == '2':
        prev_label = f'{yy}-1'
    else:
        prev_label = f'{int(yy)-1}-2'
    prev_parsed = SystemSettings.parse_label(prev_label)
    prev_display = f"{prev_parsed['sy']} — {prev_parsed['semester']}"

    import json as _json
    base_ctx = {
        'archive_types': archive_types,
        'bipsu_schools': BIPSU_SCHOOLS,
        'bipsu_courses_json': _json.dumps(BIPSU_COURSES),
        'active_type': stype,
        'history': history,
        'all_sy': all_labels,
        'all_sy_display': all_sy_display,
        'selected_sy': selected_label,
        'active_sy': active_label,
        'active_sy_display': active_display,
        'active_semester': active_semester,
        'next_sy': next_label,
        'prev_sy': prev_label,
        'prev_sy_display': prev_display,
        'add_docs': [
            (1, 'Certificate of Grades', 'Official COG from the Registrar for the previous semester.', 'doc_certificate_of_grades'),
            (2, 'Certificate of Enrollment', 'Official COE from the Registrar for the current semester.', 'doc_certificate_of_enrollment'),
            (3, 'Prospectus / Subject Checklist', 'Program prospectus or subject checklist showing enrolled subjects.', 'doc_prospectus'),
            (4, '2Ã—2 ID Photo', 'Recent 2Ã—2 ID photo with white background.', 'doc_id_photo'),
            (5, 'Application Form', 'Signed and accomplished scholarship application form.', 'doc_application_form'),
        ],
        'col_hint': COLUMN_HINTS.get(stype, ''),
        'recent_imports': ActivityLog.objects.filter(action__icontains='Imported').order_by('-created_at')[:5],
        'import_message': f"Successfully imported {request.GET.get('import_ok')} records." if request.GET.get('import_ok') else None,
        'import_error': request.GET.get('import_error'),
    }

    if stype == UNAWARDED_TAB:
        rows = _unawarded_rows(selected_label)
        return render(request, 'vpsea/archives_unawarded.html', {
            **base_ctx,
            'rows': rows,
            'total': len(rows),
        })

    # Renewal-gated: only scholars with an Approved AcademicRenewal are shown
    # For Affirmative/Staff there is no AcademicRenewal flow — show all approved
    from .models import ImportedScholar
    # Rows claimed through an approved link request are excluded — that scholar
    # now has a live Application row below, so listing both double counts them.
    imported_rows = ImportedScholar.objects.filter(
        scholarship_type=stype, term_label=selected_label, claimed_by__isnull=True,
    ).order_by('last_name', 'first_name')

    if stype in ('Affirmative', 'Staff'):
        aff_scholars = AffirmativeStaffApplication.objects.filter(
            status='Approved', qualified_for=stype
        ).order_by('full_name')
        return render(request, 'vpsea/archives.html', {
            **base_ctx,
            'aff_scholars': aff_scholars,
            'imported_rows': imported_rows,
            'scholars': None,
            'total': aff_scholars.count() + imported_rows.count(),
        })

    def sy_filter(qs):
        # The term is an indexed column now, so the selected one is simply
        # matched. The old version tried four different form_data keys — the
        # office wrote 'academic_year', the student form wrote 'school_year' —
        # and then gave up for the active term and returned every approved
        # application ever, whatever semester it belonged to.
        return qs.filter(term_label=selected_label)

    if stype == 'CHED':
        all_scholars = sy_filter(Application.objects.filter(
            status='Approved', scholarship__type='CHED',
        )).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        full_scholars, half_scholars = split_ched(all_scholars)
        return render(request, 'vpsea/archives.html', {
            **base_ctx,
            'full_scholars': full_scholars,
            'half_scholars': half_scholars,
            'imported_rows': imported_rows,
            'scholars': None,
            'total': all_scholars.count() + imported_rows.count(),
        })

    scholars = sy_filter(Application.objects.filter(
        status='Approved', scholarship__type=stype,
    )).select_related('student__user', 'scholarship').order_by('student__user__last_name').distinct()
    return render(request, 'vpsea/archives.html', {
        **base_ctx,
        'scholars': scholars,
        'imported_rows': imported_rows,
        'total': scholars.count() + imported_rows.count(),
    })


@_vpsea_required
def vpsea_archive_add(request):
    from .models import Application, Scholarship, StudentProfile, User, AffirmativeStaffApplication, SystemSettings, ApplicationDocument
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    p = request.POST
    f = request.FILES
    stype = p.get('scholarship_type', 'Academic')
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    active_semester = parsed['semester']

    if stype in ('Affirmative', 'Staff'):
        full_name = f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip()
        fake_email = f"{p.get('student_id','').strip() or full_name.replace(' ','_').lower()}_{stype.lower()}@bipsu.edu.ph"
        base = fake_email
        counter = 1
        while AffirmativeStaffApplication.objects.filter(email=fake_email).exists():
            fake_email = f"{base.split('@')[0]}_{counter}@bipsu.edu.ph"
            counter += 1
        AffirmativeStaffApplication.objects.create(
            full_name=full_name,
            email=fake_email,
            contact_number=p.get('contact_number', ''),
            barangay=p.get('barangay', ''),
            municipality=p.get('municipality', ''),
            province=p.get('province', ''),
            date_of_birth=p.get('date_of_birth') or '2000-01-01',
            gender=p.get('gender', ''),
            course=p.get('course', ''),
            year_level=int(p.get('year_level', 1) or 1),
            student_id=p.get('student_id', ''),
            qualified_for=stype,
            status='Approved',
            is_nsu_staff=(stype == 'Staff'),
        )
    else:
        email = p.get('email', '').strip()
        student_id = p.get('student_id', '').strip()
        if not email:
            email = f"{student_id}@bipsu.edu.ph"
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create_user(
                username=email, email=email,
                password=student_id or 'bipsu1234',
                first_name=p.get('first_name', ''),
                last_name=p.get('last_name', ''),
                role='student',
            )
        profile = StudentProfile.objects.filter(user=user).first()
        if not profile:
            profile = StudentProfile.objects.create(
                user=user,
                student_id=student_id,
                course=p.get('course', ''),
                year_level=int(p.get('year_level', 1) or 1),
                gwa=float(p.get('gwa', 0) or 0),
                gender=p.get('gender', ''),
                barangay=p.get('barangay', ''),
                municipality=p.get('municipality', ''),
                province=p.get('province', ''),
                contact_number=p.get('contact_number', ''),
                date_of_birth=p.get('date_of_birth') or None,
            )
        else:
            profile.course = p.get('course', profile.course)
            profile.year_level = int(p.get('year_level', profile.year_level) or profile.year_level)
            profile.gwa = float(p.get('gwa', profile.gwa) or profile.gwa)
            profile.gender = p.get('gender', profile.gender)
            profile.barangay = p.get('barangay', profile.barangay)
            profile.municipality = p.get('municipality', profile.municipality)
            profile.province = p.get('province', profile.province)
            profile.save()
        scholarship = Scholarship.objects.filter(type=stype).first()
        if scholarship:
            award_fields = {
                'source': 'import',
                'school_year': active_sy,
                'semester': active_semester,
                'award_number': p.get('award_number', ''),
                'congress_district': p.get('congress_district', ''),
            }
            form_data = {}
            if stype == 'Academic':
                form_data.update({
                    'elementary': p.get('elementary', ''),
                    'highschool': p.get('highschool', ''),
                    'last_school': p.get('last_school', ''),
                    'father_name': p.get('father_name', ''),
                    'father_occupation': p.get('father_occupation', ''),
                    'mother_name': p.get('mother_name', ''),
                    'mother_occupation': p.get('mother_occupation', ''),
                })
            already = Application.objects.filter(
                student=profile, scholarship=scholarship,
                school_year=active_sy, semester=active_semester,
            ).exists()
            if not already:
                app = Application.objects.create(
                    student=profile,
                    scholarship=scholarship,
                    status='Approved',
                    form_data=form_data,
                    **award_fields,
                )
            else:
                app = Application.objects.filter(
                    student=profile, scholarship=scholarship,
                    school_year=active_sy, semester=active_semester,
                ).first()
            # Save uploaded documents
            doc_fields = [
                ('doc_certificate_of_grades', 'Certificate Of Grades'),
                ('doc_certificate_of_enrollment', 'Certificate Of Enrollment'),
                ('doc_prospectus', 'Prospectus'),
                ('doc_id_photo', 'Id Photo'),
                ('doc_application_form', 'Application Form'),
                ('proof_document', 'Proof Document'),
            ]
            for field, label in doc_fields:
                uploaded = f.get(field)
                if uploaded:
                    ApplicationDocument.objects.create(application=app, name=label, file=uploaded)
    return redirect(f'/vpsea/archives/?type={stype}&added=1')


def _apply_student_record_edits(profile, p):
    """Correct a student's own details — the typo fixing the archives screens do.

    Shared by the scholarship tabs, which reach a student through their
    Application, and the No Scholarship tab, which has no application to reach
    through. One implementation, so the same Edit button means the same thing
    wherever it is opened.

    Returns an error string, or '' when the edits were saved.
    """
    from .models import StudentProfile

    user = profile.user
    new_sid = (p.get('student_id') or '').strip()
    if (new_sid and new_sid != profile.student_id
            and StudentProfile.objects.filter(student_id=new_sid).exclude(pk=profile.pk).exists()):
        # student_id is unique at the database level; without this the office
        # would get a 500 instead of being told what went wrong.
        return f'Student number {new_sid} already belongs to another student.'

    user.first_name = p.get('first_name', user.first_name)
    user.last_name = p.get('last_name', user.last_name)
    new_pw = (p.get('new_password') or '').strip()
    if new_pw:
        user.set_password(new_pw)
    user.save()

    profile.course = p.get('course', profile.course)
    if p.get('school'):
        profile.school = p.get('school')
    profile.year_level = int(p.get('year_level', profile.year_level) or profile.year_level)
    profile.gender = p.get('gender', profile.gender)
    profile.barangay = p.get('barangay', profile.barangay)
    profile.municipality = p.get('municipality', profile.municipality)
    profile.province = p.get('province', profile.province)
    if new_sid:
        profile.student_id = new_sid
    if p.get('contact_number'):
        profile.contact_number = p.get('contact_number')
    if p.get('gwa'):
        profile.gwa = float(p.get('gwa'))

    # Civil status, educational background and family background lock for the
    # student after their first save. This screen is the office's way to fix one
    # that was entered wrong, so here they stay writable — but only fields the
    # form actually submitted, so a modal that omits them changes nothing.
    for field in ('civil_status', 'elementary', 'highschool', 'last_school',
                  'father_last_name', 'father_first_name', 'father_middle_name',
                  'father_occupation', 'mother_last_name', 'mother_first_name',
                  'mother_middle_name', 'mother_occupation'):
        value = (p.get(field) or '').strip()
        if value:
            setattr(profile, field, value)

    profile.save()
    return ''


@_vpsea_required
def vpsea_student_record_edit(request, pk):
    """Edit a student who holds no award, from the No Scholarship tab.

    Same edits as the scholarship tabs, reached by StudentProfile instead of
    Application — these students have no application to key off.
    """
    from .models import StudentProfile
    from urllib.parse import quote
    back = f'/vpsea/archives/?type={quote(UNAWARDED_TAB)}'
    if request.method != 'POST':
        return redirect(back)
    profile = StudentProfile.objects.select_related('user').filter(pk=pk).first()
    if not profile:
        return redirect(back)
    error = _apply_student_record_edits(profile, request.POST)
    if error:
        return redirect(f'{back}&error={quote(error)}')
    return redirect(f'{back}&edited=1')


@_vpsea_required
def vpsea_archive_edit(request, pk):
    from .models import Application, AffirmativeStaffApplication, StudentProfile, SystemSettings
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    p = request.POST
    stype = p.get('scholarship_type', 'Academic')
    is_aff = stype in ('Affirmative', 'Staff')

    if is_aff:
        try:
            obj = AffirmativeStaffApplication.objects.get(pk=pk)
        except AffirmativeStaffApplication.DoesNotExist:
            return redirect(f'/vpsea/archives/?type={stype}')
        obj.full_name = f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip()
        obj.gender = p.get('gender', obj.gender)
        obj.course = p.get('course', obj.course)
        if p.get('school'):
            obj.school = p.get('school')
        obj.year_level = int(p.get('year_level', obj.year_level) or obj.year_level)
        obj.barangay = p.get('barangay', obj.barangay)
        obj.municipality = p.get('municipality', obj.municipality)
        obj.province = p.get('province', obj.province)
        obj.student_id = p.get('student_id', obj.student_id)
        if p.get('contact_number'):
            obj.contact_number = p.get('contact_number')
        if p.get('date_of_birth'):
            obj.date_of_birth = p.get('date_of_birth')
        # Password reset for AffirmativeStaffApplication scholars
        new_pw = p.get('new_password', '').strip()
        if new_pw:
            obj.set_password(new_pw)
        obj.save()
    else:
        try:
            app = Application.objects.select_related('student__user').get(pk=pk)
        except Application.DoesNotExist:
            return redirect(f'/vpsea/archives/?type={stype}')
        error = _apply_student_record_edits(app.student, p)
        if error:
            from urllib.parse import quote
            return redirect(f'/vpsea/archives/?type={stype}&error={quote(error)}')
        if p.get('award_number') is not None:
            app.award_number = p.get('award_number')
        if p.get('congress_district') is not None:
            app.congress_district = p.get('congress_district')
        app.save()
    return redirect(f'/vpsea/archives/?type={stype}&edited=1')


@_vpsea_required
def vpsea_archive_delete(request, pk):
    from .models import Application, AffirmativeStaffApplication
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('scholarship_type', 'Academic')
    if stype in ('Affirmative', 'Staff'):
        AffirmativeStaffApplication.objects.filter(pk=pk).delete()
    else:
        Application.objects.filter(pk=pk).delete()
    return redirect(f'/vpsea/archives/?type={stype}&deleted=1')


@_vpsea_required
def vpsea_new_semester(request):
    from .models import SystemSettings, ScholarListImport, ActivityLog, Application, AffirmativeStaffApplication
    from django.core.files.base import ContentFile
    import openpyxl
    from io import BytesIO
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    label = request.POST.get('school_year', '').strip()
    stype = request.POST.get('type', 'Academic')
    if not label or '-' not in label:
        return redirect(f'/vpsea/archives/?type={stype}')

    parsed = SystemSettings.parse_label(label)
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    settings_obj.academic_year = label
    settings_obj.active_semester = parsed['semester']
    settings_obj.save()

    _base = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    ALL_TYPES = _base + [t for t in Scholarship.objects.values_list('type', flat=True).distinct() if t not in _base]

    def _build_excel(scholarship_type):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Scholars'
        if scholarship_type in ('Affirmative', 'Staff'):
            ws.append(['No.', 'Full Name', 'Gender', 'Course', 'Year Level', 'Student ID', 'Address'])
            qs = AffirmativeStaffApplication.objects.filter(
                status='Approved', qualified_for=scholarship_type
            ).order_by('full_name')
            for i, s in enumerate(qs, 1):
                ws.append([i, s.full_name, s.gender, s.course, s.year_level, s.student_id, s.address])
        else:
            ws.append(['No.', 'Last Name', 'First Name', 'Gender', 'Course', 'Year Level', 'Student ID', 'GWA', 'Barangay', 'Municipality', 'Province'])
            qs = Application.objects.filter(
                status='Approved', scholarship__type=scholarship_type
            ).select_related('student__user').order_by('student__user__last_name')
            for i, app in enumerate(qs, 1):
                p = app.student
                ws.append([i, p.user.last_name, p.user.first_name, p.gender, p.course, p.year_level, p.student_id, p.gwa, p.barangay, p.municipality, p.province])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf, qs.count()

    created = 0
    for t in ALL_TYPES:
        if ScholarListImport.objects.filter(term_label=label, scholarship_type=t).exists():
            continue
        buf, count = _build_excel(t)
        rollover = ScholarListImport(
            scholarship_type=t,
            school_year=parsed['sy'],
            semester=parsed['semester'],
            term_label=label,
            scholar_count=count,
            imported_by=request.user,
        )
        rollover.excel_file.save(f'{t}_{label}.xlsx', ContentFile(buf.read()), save=True)
        created += 1

    ActivityLog.objects.create(
        user=request.user,
        action=f'New semester started: {label} ({parsed["sy"]} {parsed["semester"]}). Saved lists for {created} scholarship types.'
    )
    return redirect(f'/vpsea/archives/?type={stype}')


@_vpsea_required
def vpsea_undo_semester(request):
    from .models import SystemSettings, ActivityLog
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    prev_label = request.POST.get('prev_label', '').strip()
    stype = request.POST.get('type', 'Academic')
    if not prev_label or '-' not in prev_label:
        return redirect(f'/vpsea/archives/?type={stype}')
    parsed = SystemSettings.parse_label(prev_label)
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    old_label = settings_obj.academic_year
    settings_obj.academic_year = prev_label
    settings_obj.active_semester = parsed['semester']
    settings_obj.save()
    ActivityLog.objects.create(
        user=request.user,
        action=f'Semester undone from {old_label} back to {prev_label} ({parsed["sy"]} {parsed["semester"]}).'
    )
    return redirect(f'/vpsea/archives/?type={stype}')


COLUMN_HINTS = {
    'Academic':    'No. | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Course | Year | GWA | % / Type | Scholarship',
    'Staff':       'No. | Last Name | First Name | Middle Initial | Sex | Course | Year Level | Student Number | % | Scholarship Program',
    'CHED':        'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'TDP':         'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'DOST':        'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'GSIS':        'No. | Last Name | First Name | Middle Initial | Brgy./St. | Municipality | Province | Sex | Course | Year Level | Student Number | Scholarship Program',
    'Affirmative': 'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'CoScho':      'No. | Last Name | First Name | Middle Initial | Sex | Brgy./St. | Municipality | Province | Course | Year Level | Student Number | Scholarship Program',
    'Sports':      'No. | Last Name | First Name | Middle Initial | Sex | Brgy./St. | Municipality | Province | Course | Year Level | Student Number | Scholarship Program',
}

COLUMN_MAPS = {
    'Academic':    [(1,'last_name'),(2,'first_name'),(3,'middle_name'),(4,'sex'),(5,'barangay'),(6,'municipality'),(7,'province'),(8,'course'),(9,'year'),(10,'gwa'),(11,'pct_type'),(12,'scholarship')],
    'Staff':       [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'sex'),(5,'course'),(6,'year'),(7,'student_number'),(8,'pct'),(9,'scholarship_program')],
    'CHED':        [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'TDP':         [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'DOST':        [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'GSIS':        [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'barangay'),(5,'municipality'),(6,'province'),(7,'sex'),(8,'course'),(9,'year'),(10,'student_number'),(11,'scholarship_program')],
    'Affirmative': [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'CoScho':      [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'sex'),(5,'barangay'),(6,'municipality'),(7,'province'),(8,'course'),(9,'year'),(10,'student_number'),(11,'scholarship_program')],
    'Sports':      [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'sex'),(5,'barangay'),(6,'municipality'),(7,'province'),(8,'course'),(9,'year'),(10,'student_number'),(11,'scholarship_program')],
}


@_vpsea_required
def vpsea_rollover_delete(request, pk):
    from .models import ScholarListImport
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('type', 'Academic')
    try:
        r = ScholarListImport.objects.get(pk=pk)
        r.excel_file.delete(save=False)
        r.delete()
    except ScholarListImport.DoesNotExist:
        pass
    return redirect(f'/vpsea/archives/?type={stype}')


@_vpsea_required
def vpsea_archive_import(request):
    import openpyxl
    from django.core.files.base import ContentFile
    from .models import ScholarListImport, ActivityLog, SystemSettings, ImportedScholar
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('type', 'Academic')
    rollover_label = request.POST.get('rollover_label', '').strip()
    file = request.FILES.get('file')
    if not file:
        return redirect(f'/vpsea/archives/?type={stype}&import_error=No+file+provided')
    if not rollover_label:
        return redirect(f'/vpsea/archives/?type={stype}&import_error=Rollover+name+is+required')
    try:
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        parsed = SystemSettings.parse_label(settings_obj.academic_year)
        active_semester = parsed['semester']
        rollover_parsed = SystemSettings.parse_label(rollover_label) if '-' in rollover_label else {'sy': rollover_label, 'semester': active_semester}

        wb = openpyxl.load_workbook(file)
        ws = wb.active
        col_map = COLUMN_MAPS.get(stype, COLUMN_MAPS['CoScho'])

        # Delete existing rows for this label+type so re-import is clean
        ImportedScholar.objects.filter(scholarship_type=stype, term_label=rollover_label).delete()

        records = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue
            try:
                int(row[0])
            except (ValueError, TypeError):
                continue

            extra = {}
            for idx, field in col_map:
                val = row[idx] if idx < len(row) else None
                extra[field] = str(val).strip() if val is not None else ''

            last = extra.get('last_name', '').strip()
            first = extra.get('first_name', '').strip()
            if not last and not first:
                continue

            try:
                year_level = int(extra.get('year', 0) or 0)
            except (ValueError, TypeError):
                year_level = 0
            try:
                gwa = float(extra.get('gwa', 0) or 0)
            except (ValueError, TypeError):
                gwa = 0.0

            address = extra.get('address', '')
            addr_parts = [x.strip() for x in address.split(',')] if address else []

            records.append(ImportedScholar(
                scholarship_type=stype,
                term_label=rollover_label,
                last_name=last,
                first_name=first,
                middle_name=extra.get('middle_name', extra.get('middle_initial', '')),
                gender=extra.get('sex', ''),
                course=extra.get('course', ''),
                year=year_level,
                gwa=gwa,
                barangay=extra.get('barangay', addr_parts[0] if len(addr_parts) > 0 else ''),
                municipality=extra.get('municipality', addr_parts[1] if len(addr_parts) > 1 else ''),
                province=extra.get('province', addr_parts[2] if len(addr_parts) > 2 else ''),
                student_id=extra.get('student_number', extra.get('student_id', '')),
                award_number=extra.get('award_number', ''),
                congress_district=extra.get('congress_district', ''),
                imported_from=file.name,
            ))

        ImportedScholar.objects.bulk_create(records)
        created = len(records)

        # Save the uploaded file as a rollover record for download history
        file.seek(0)
        if not ScholarListImport.objects.filter(term_label=rollover_label, scholarship_type=stype).exists():
            rollover = ScholarListImport(
                scholarship_type=stype,
                school_year=rollover_parsed['sy'],
                semester=rollover_parsed.get('semester', active_semester),
                term_label=rollover_label,
                scholar_count=created,
                imported_by=request.user,
            )
            rollover.excel_file.save(f'{stype}_{rollover_label}.xlsx', ContentFile(file.read()), save=True)
        else:
            ScholarListImport.objects.filter(term_label=rollover_label, scholarship_type=stype).update(scholar_count=created)

        ActivityLog.objects.create(
            user=request.user,
            action=f'Imported {file.name} ({created} rows) for {stype} as "{rollover_label}"'
        )
    except Exception as e:
        return redirect(f'/vpsea/archives/?type={stype}&import_error={e}')
    return redirect(f'/vpsea/archives/?type={stype}&import_ok={created}')



@_vpsea_required
def vpsea_archive_download(request):
    from .models import Application, AffirmativeStaffApplication, SystemSettings, AcademicRenewal
    stype = request.GET.get('type', 'Academic')
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    school_year = settings_obj.academic_year
    semester = settings_obj.active_semester

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'{stype} Scholars'
    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    hfont = Font(bold=True)
    hfill = PatternFill('solid', fgColor='D9E1F2')

    def hrow(ws, r, n):
        for c in range(1, n+1):
            cell = ws.cell(row=r, column=c)
            cell.font = hfont; cell.fill = hfill; cell.border = border; cell.alignment = center

    def drow(ws, r, vals):
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = border
            cell.alignment = Alignment(vertical='center', wrap_text=True)

    def name_parts(user):
        return user.last_name or '', user.first_name or '', ''

    def split_name(full):
        p = full.strip().split()
        if len(p) == 0: return '', '', ''
        if len(p) == 1: return p[0], '', ''
        if len(p) == 2: return p[-1], p[0], ''
        return p[-1], p[0], ' '.join(p[1:-1])[0] + '.'

    renewed_ids = AcademicRenewal.objects.filter(status='Approved').values_list('student_id', flat=True)

    row = 1
    if stype in ('Affirmative', 'Staff'):
        scholars = AffirmativeStaffApplication.objects.filter(status='Approved', qualified_for=stype).order_by('full_name')
        if stype == 'Staff':
            headers = ['No.', 'Last', 'First', 'M.I.', 'Sex', 'Course', 'Year Level', 'Student No.', '%', 'Scholarship Program']
        else:
            headers = ['No.', 'Last Name', 'First Name', 'Middle Name', 'Sex', 'Address', 'Course', 'Yr.', 'Scholarship Program']
        ws.append(headers); hrow(ws, row, len(headers)); row += 1
        for i, app in enumerate(scholars, 1):
            last, first, mi = split_name(app.full_name)
            if stype == 'Staff':
                drow(ws, row, [i, last, first, mi, app.gender, app.course, app.year_level, app.student_id, '100%' if app.is_nsu_staff else '75%', 'BiPSU Staff Scholarship'])
            else:
                drow(ws, row, [i, last, first, mi, app.gender, app.address, app.course, app.year_level, 'Affirmative Action Scholarship'])
            row += 1
    elif stype == 'Academic':
        scholars = Application.objects.filter(status='Approved', scholarship__type='Academic', student_id__in=renewed_ids).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        headers = ['No.', 'Last Name', 'First', 'Middle Name', 'Sex', 'Brgy./St.', 'Municipality', 'Province', 'Course', 'Yr', 'GWA', '% / Type', 'Scholarship']
        ws.append(headers); hrow(ws, row, len(headers)); row += 1
        for i, app in enumerate(scholars, 1):
            p = app.student; last, first, mi = name_parts(p.user)
            pct = 'University Scholar' if p.gwa <= 1.29 else ('College Scholar' if p.gwa <= 1.50 else '')
            drow(ws, row, [i, last, first, mi, p.gender, p.barangay, p.municipality, p.province, p.course, p.year_level, p.gwa, pct, app.scholarship.name]); row += 1
    else:
        scholars = Application.objects.filter(status='Approved', scholarship__type=stype, student_id__in=renewed_ids).select_related('student__user', 'scholarship').order_by('student__user__last_name')
        headers = ['No.', 'Last Name', 'First Name', 'Middle Name', 'Sex', 'Brgy./St.', 'Municipality', 'Province', 'Course', 'Year', 'Student No.', 'Scholarship Program']
        ws.append(headers); hrow(ws, row, len(headers)); row += 1
        for i, app in enumerate(scholars, 1):
            p = app.student; last, first, mi = name_parts(p.user)
            drow(ws, row, [i, last, first, mi, p.gender, p.barangay, p.municipality, p.province, p.course, p.year_level, p.student_id, app.scholarship.name]); row += 1

    for col in ws.columns:
        ml = max((len(str(c.value)) for c in col if c.value), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(ml + 4, 40)

    buf = BytesIO(); wb.save(buf); buf.seek(0)
    filename = f'{stype}_scholars_{school_year}_{semester.replace(" ", "_")}.xlsx'
    response = HttpResponse(buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response



def _analytics_context(request, all_types, include_gwa=True):
    """Build the analytics context for a given set of scholarship types.

    Shared by the VPSEA portal (every type) and the UniFAST portal (TES and TDP
    only), so both read the same numbers from the same code path.
    """
    from .models import ScholarListImport, SystemSettings
    import openpyxl
    from collections import defaultdict

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    ALL_TYPES = list(all_types)

    from .models import ImportedScholar
    all_labels = list(
        ScholarListImport.objects.values_list('term_label', flat=True)
        .distinct().order_by('-term_label')
    )
    # Also include labels that only exist in ImportedScholar (import-only semesters)
    ar_labels = list(
        ImportedScholar.objects.exclude(term_label='')
        .values_list('term_label', flat=True).distinct()
    )
    for lbl in ar_labels:
        if lbl not in all_labels:
            all_labels.append(lbl)
    all_labels = sorted(set(all_labels), reverse=True)
    if active_label not in all_labels:
        all_labels.insert(0, active_label)
    all_sy_display = [(lbl, f"{SystemSettings.parse_label(lbl)['sy']} — {SystemSettings.parse_label(lbl)['semester']}") for lbl in all_labels]

    selected_label = request.GET.get('sy', active_label)
    if selected_label not in all_labels:
        selected_label = active_label
    selected_parsed = SystemSettings.parse_label(selected_label)
    selected_sy = selected_parsed['sy']
    selected_semester = selected_parsed['semester']
    selected_type = request.GET.get('stype', '')

    # Scholar count per type: rollover records + ImportedScholar imports
    from .models import ImportedScholar
    # Scholar count per type: if selected = active semester, use live DB counts
    # otherwise use ImportedScholar imports or ScholarListImport snapshot
    rollover_counts = {}
    for t in ALL_TYPES:
        if selected_label == active_label:
            # Current semester — no rollover yet, count from live approved records
            if t in ('Affirmative', 'Staff'):
                from .models import AffirmativeStaffApplication
                rollover_counts[t] = AffirmativeStaffApplication.objects.filter(
                    status='Approved', qualified_for=t
                ).count()
            else:
                rollover_counts[t] = Application.objects.filter(
                    status='Approved', scholarship__type=t
                ).count()
        else:
            # Past semester — prefer ImportedScholar rows, fall back to rollover snapshot
            import_count = ImportedScholar.objects.filter(scholarship_type=t, term_label=selected_label).count()
            if import_count:
                rollover_counts[t] = import_count
            else:
                r = ScholarListImport.objects.filter(scholarship_type=t, term_label=selected_label).first()
                rollover_counts[t] = r.scholar_count if r else 0

    def _course_counts_from_rollover(stype):
        # Current semester — pull from live approved records
        if selected_label == active_label:
            from django.db.models import Count as DCount
            if stype in ('Affirmative', 'Staff'):
                from .models import AffirmativeStaffApplication
                qs = AffirmativeStaffApplication.objects.filter(
                    status='Approved', qualified_for=stype
                ).values('course').annotate(n=DCount('id'))
                return {r['course'] or 'Unknown': r['n'] for r in qs}
            else:
                qs = Application.objects.filter(
                    status='Approved', scholarship__type=stype
                ).values('student__course').annotate(n=DCount('id'))
                return {r['student__course'] or 'Unknown': r['n'] for r in qs}
        # Past semester — first try ImportedScholar (imported rows)
        ar_counts = {}
        for rec in ImportedScholar.objects.filter(scholarship_type=stype, term_label=selected_label).values('course'):
            c = rec['course'] or 'Unknown'
            ar_counts[c] = ar_counts.get(c, 0) + 1
        if ar_counts:
            return ar_counts
        # Fall back to rollover excel file
        r = ScholarListImport.objects.filter(scholarship_type=stype, term_label=selected_label).first()
        if not r or not r.excel_file:
            return {}
        try:
            wb = openpyxl.load_workbook(r.excel_file.path)
            ws = wb.active
            course_col = next((cell.column - 1 for cell in ws[1] if cell.value and 'course' in str(cell.value).lower()), None)
            if course_col is None:
                return {}
            counts = defaultdict(int)
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[0] is not None and course_col < len(row) and row[course_col]:
                    counts[str(row[course_col]).strip()] += 1
            return dict(counts)
        except Exception:
            return {}

    # Course distribution
    if selected_type and selected_type in ALL_TYPES:
        raw = _course_counts_from_rollover(selected_type)
    else:
        raw = defaultdict(int)
        for t in ALL_TYPES:
            for k, v in _course_counts_from_rollover(t).items():
                raw[k] += v
    course_dist = [{'course': k, 'scholars': v} for k, v in sorted(raw.items(), key=lambda x: -x[1])]

    # GWA distribution — current sem: live DB; past sem: ImportedScholar or rollover excel
    gpa_ranges = [{'range': r, 'count': 0} for r in ['1.00-1.25', '1.26-1.50', '1.51-1.75', '1.76-2.00', '2.01-2.50']]
    if not include_gwa:
        # TES and TDP are needs-based — they are not banded by GWA.
        gpa_ranges = []
    elif selected_label == active_label:
        buckets = {'1.00-1.25': 0, '1.26-1.50': 0, '1.51-1.75': 0, '1.76-2.00': 0, '2.01-2.50': 0}
        for p in Application.objects.filter(
            status='Approved', scholarship__type='Academic'
        ).values('student__gwa'):
            g = p['student__gwa'] or 0
            if 1.0 <= g <= 1.25: buckets['1.00-1.25'] += 1
            elif g <= 1.50: buckets['1.26-1.50'] += 1
            elif g <= 1.75: buckets['1.51-1.75'] += 1
            elif g <= 2.00: buckets['1.76-2.00'] += 1
            elif g <= 2.50: buckets['2.01-2.50'] += 1
        gpa_ranges = [{'range': k, 'count': v} for k, v in buckets.items()]
    else:
        ar_academic = ImportedScholar.objects.filter(scholarship_type='Academic', term_label=selected_label)
        if ar_academic.exists():
            buckets = {'1.00-1.25': 0, '1.26-1.50': 0, '1.51-1.75': 0, '1.76-2.00': 0, '2.01-2.50': 0}
            for rec in ar_academic.values('gwa'):
                g = rec['gwa'] or 0
                if 1.0 <= g <= 1.25: buckets['1.00-1.25'] += 1
                elif g <= 1.50: buckets['1.26-1.50'] += 1
                elif g <= 1.75: buckets['1.51-1.75'] += 1
                elif g <= 2.00: buckets['1.76-2.00'] += 1
                elif g <= 2.50: buckets['2.01-2.50'] += 1
            gpa_ranges = [{'range': k, 'count': v} for k, v in buckets.items()]
        else:
            acad_r = ScholarListImport.objects.filter(scholarship_type='Academic', term_label=selected_label).first()
            if acad_r and acad_r.excel_file:
                try:
                    wb = openpyxl.load_workbook(acad_r.excel_file.path)
                    ws = wb.active
                    gwa_col = next((cell.column - 1 for cell in ws[1] if cell.value and 'gwa' in str(cell.value).lower()), None)
                    if gwa_col is not None:
                        buckets = {'1.00-1.25': 0, '1.26-1.50': 0, '1.51-1.75': 0, '1.76-2.00': 0, '2.01-2.50': 0}
                        for row in ws.iter_rows(min_row=2, values_only=True):
                            if row and row[0] is not None:
                                try:
                                    g = float(row[gwa_col]) if gwa_col < len(row) and row[gwa_col] else 0
                                    if 1.0 <= g <= 1.25: buckets['1.00-1.25'] += 1
                                    elif g <= 1.50: buckets['1.26-1.50'] += 1
                                    elif g <= 1.75: buckets['1.51-1.75'] += 1
                                    elif g <= 2.00: buckets['1.76-2.00'] += 1
                                    elif g <= 2.50: buckets['2.01-2.50'] += 1
                                except (ValueError, TypeError):
                                    pass
                        gpa_ranges = [{'range': k, 'count': v} for k, v in buckets.items()]
                except Exception:
                    pass

    # ── Scholars-over-time trend ──────────────────────────────────────────────
    # Build a chronological list of (label, display, total_scholars) covering
    # every known semester so the line chart spans the full history.
    # Labels use the compact format "YY-S" (e.g. "25-1") — sort numerically.
    def _label_sort_key(lbl):
        try:
            yy, s = lbl.split('-')
            return int(yy) * 10 + int(s)
        except Exception:
            return 0

    trend_labels_sorted = sorted(set(all_labels), key=_label_sort_key)

    trend_data = []
    for lbl in trend_labels_sorted:
        parsed = SystemSettings.parse_label(lbl)
        display = f"{parsed['sy']}\n{parsed['semester']}"   # two-line label for x-axis
        short   = f"{parsed['sy']} S{parsed['sy_start'] and lbl.split('-')[1] or '?'}"

        # One pass per semester. The total and the per-programme breakdown are
        # the same counts, and this used to run every one of these queries twice
        # to produce both.
        counts = {}
        for t in ALL_TYPES:
            if lbl == active_label:
                if t in ('Affirmative', 'Staff'):
                    from .models import AffirmativeStaffApplication
                    c = AffirmativeStaffApplication.objects.filter(
                        status='Approved', qualified_for=t
                    ).count()
                else:
                    c = Application.objects.filter(
                        status='Approved', scholarship__type=t
                    ).count()
            else:
                # Prefer ImportedScholar row count, fall back to rollover snapshot
                c = ImportedScholar.objects.filter(
                    scholarship_type=t, term_label=lbl
                ).count()
                if not c:
                    r = ScholarListImport.objects.filter(
                        scholarship_type=t, term_label=lbl
                    ).first()
                    c = r.scholar_count if r else 0
            counts[t] = c

        parsed_display = f"{parsed['sy']} — {parsed['semester']}"
        trend_data.append({
            'label': lbl,
            'display': parsed_display,
            'total': sum(counts.values()),
            'counts': counts,
            'per_type': {t: c for t, c in counts.items() if c},
        })

    # One line per programme rather than a single blended total: the total is
    # what the summary tiles already say, while the comparison between
    # programmes is what this chart is for. A programme with no scholars in a
    # semester contributes a zero rather than a gap, so the lines stay aligned;
    # a programme with no scholars in any semester is left out entirely.
    # Filtering the page to one programme draws that one alone.
    if selected_type and selected_type in ALL_TYPES:
        series_types = [selected_type]
    else:
        series_types = [t for t in ALL_TYPES
                        if any(d['counts'].get(t) for d in trend_data)]
    trend_series = [
        {'type': t, 'counts': [d['counts'].get(t, 0) for d in trend_data]}
        for t in series_types
    ]

    return {
        'rollover_counts': rollover_counts,
        'all_types': ALL_TYPES,
        'course_dist': course_dist,
        'gpa_ranges': gpa_ranges,
        'all_sy_display': all_sy_display,
        'selected_sy': selected_label,
        'selected_type': selected_type,
        'selected_sy_display': f"{selected_sy} — {selected_semester}",
        'active_sy': active_label,
        'trend_data': trend_data,
        'trend_series': trend_series,
    }


@_vpsea_required
def vpsea_analytics(request):
    """Every scholarship type, GWA distribution included."""
    _base = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    all_types = _base + [
        t for t in Scholarship.objects.values_list('type', flat=True).distinct()
        if t not in _base
    ]
    return render(request, 'vpsea/analytics.html', _analytics_context(request, all_types))


@_unifast_required
def unifast_analytics(request):
    """Scoped to the programmes UniFAST administers: TES and TDP."""
    ctx = _analytics_context(request, UNIFAST_TYPES, include_gwa=False)
    return render(request, 'unifast/analytics.html', ctx)


@_unifast_required
def unifast_announcements(request):
    from .models import Announcement
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        body = (request.POST.get('body') or '').strip()
        if title and body:
            Announcement.objects.create(title=title, body=body, published_by=request.user)
            return redirect('/unifast/announcements/?posted=1')
        return render(request, 'unifast/announcements.html', {
            'announcements': Announcement.objects.select_related('published_by').order_by('-created_at'),
            'errors': ['Both a title and a body are required.'],
            'post': request.POST,
        })
    return render(request, 'unifast/announcements.html', {
        'announcements': Announcement.objects.select_related('published_by').order_by('-created_at'),
        'posted': request.GET.get('posted'),
    })


def _unifast_report_sections():
    """Approved TES and TDP scholars, split by gender, in masterlist order.

    Mirrors the VPSEA report layout but covers only the two programmes UniFAST
    administers. Both are sourced from approved Applications — TES rows are
    created when a TES application is approved in this portal.
    """
    def _row(app):
        p = app.student
        u = p.user
        return {
            'last': u.last_name, 'first': u.first_name, 'mi': '',
            'sex': p.gender or '', 'brgy': p.barangay, 'mun': p.municipality,
            'prov': p.province, 'course': p.course, 'yr': p.year_level,
            'student_no': p.student_id,
            'scholarship': app.scholarship.name,
            'award': app.award_number,
            'cong': app.congress_district,
        }

    def _split_gender(apps):
        female = [_row(a) for a in apps if (a.student.gender or '').upper() in ('F', 'FEMALE')]
        male = [_row(a) for a in apps if (a.student.gender or '').upper() not in ('F', 'FEMALE')]
        return female, male

    headers = ['NO.', 'AWARD NO.', 'LAST NAME', 'FIRST NAME', 'M.I.', 'SEX',
               'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'STUDENT NO.',
               'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    sections = []
    for stype, title in (
        ('TDP', 'TDP — TULONG DUNONG PROGRAM'),
        ('TES', 'TES — TERTIARY EDUCATION SUBSIDY'),
    ):
        apps = list(
            Application.objects.filter(status='Approved', scholarship__type=stype)
            .select_related('student__user', 'scholarship')
            .order_by('student__user__last_name')
        )
        female, male = _split_gender(apps)
        sections.append({
            'title': title, 'key': stype.lower(), 'headers': headers,
            'groups': [('FEMALE', female), ('MALE', male)],
            'female_rows': female, 'male_rows': male,
            'total': len(apps),
        })
    return sections


@_unifast_required
def unifast_reports(request):
    """On-screen replica of the CHED 'Official List' validation sheet."""
    import os
    from .models import SystemSettings
    from . import tes_report

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    batch = request.GET.get('batch', '').strip()
    rows = tes_report.grantee_rows(batch=batch)
    sections = _unifast_report_sections()

    return render(request, 'unifast/reports.html', {
        'rows': rows,
        'headers': tes_report.OFFICIAL_LIST_HEADERS,
        'batch': batch,
        'semester': parsed['semester'],
        'ay': parsed['sy'],
        'tes_total': len(rows),
        'pwd_count': sum(1 for r in rows if r['is_pwd']),
        'template_available': os.path.exists(tes_report.TEMPLATE_PATH),
        # The plain TDP/TES masterlist stays available underneath.
        'sections': sections,
        'grand_total': sum(s['total'] for s in sections),
        'error': request.GET.get('error'),
    })


@_unifast_required
def unifast_report_download_tes(request):
    """The filled CHED TES validation & billing workbook, all four sheets."""
    from .models import SystemSettings
    from . import tes_report

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    batch = request.GET.get('batch', '').strip()
    try:
        buf, written, overflow = tes_report.build_workbook(
            parsed['sy'], parsed['semester'], batch=batch)
    except FileNotFoundError as exc:
        from urllib.parse import quote
        return redirect(f'/unifast/reports/?error={quote(str(exc))}')

    label = settings_obj.academic_year.replace('-', '_')
    filename = f'TES_Validation_Billing_{label}.xlsx'
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    if overflow:
        response['X-TES-Overflow'] = str(overflow)
    return response


@_unifast_required
def unifast_report_download_excel(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from .models import SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    semester, ay = parsed['semester'], parsed['sy']

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'UniFAST Scholars'

    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    row_at = [1]

    def banner(text, ncols, fill, font, height=None):
        r = row_at[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font, cell.fill, cell.alignment, cell.border = font, fill, center, border
        if height:
            ws.row_dimensions[r].height = height
        row_at[0] += 1

    def label(text, ncols):
        r = row_at[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        ws.cell(row=r, column=1).font = Font(bold=True, size=9)
        row_at[0] += 1

    def table(headers, rows):
        r = row_at[0]
        for ci, h in enumerate(headers, 1):
            cell = ws.cell(row=r, column=ci, value=h)
            cell.font = Font(bold=True, size=9)
            cell.fill = PatternFill('solid', fgColor='D9E1F2')
            cell.alignment, cell.border = center, border
        row_at[0] += 1
        for i, row in enumerate(rows, 1):
            r = row_at[0]
            values = [i, row['award'], row['last'], row['first'], row['mi'], row['sex'],
                      row['brgy'], row['mun'], row['prov'], row['cong'],
                      row['student_no'], row['course'], row['yr'], row['scholarship']]
            for ci, val in enumerate(values, 1):
                cell = ws.cell(row=r, column=ci, value=val)
                cell.font = Font(size=9)
                cell.border = border
            row_at[0] += 1
        if not rows:
            r = row_at[0]
            ws.cell(row=r, column=1, value='No approved scholars for this programme.')
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(headers))
            ws.cell(row=r, column=1).font = Font(size=9, italic=True)
            row_at[0] += 1
        row_at[0] += 1

    sections = _unifast_report_sections()
    ncols = len(sections[0]['headers'])
    banner(f'BILIRAN PROVINCE STATE UNIVERSITY — UniFAST SCHOLARS  |  {ay} {semester}',
           ncols, PatternFill('solid', fgColor='1F4E79'),
           Font(bold=True, size=11, color='FFFFFF'), height=18)
    row_at[0] += 1

    for section in sections:
        banner(f"{section['title']}  ({section['total']} scholars)", ncols,
               PatternFill('solid', fgColor='BDD7EE'), Font(bold=True, size=10))
        label('FEMALE', ncols)
        table(section['headers'], section['female_rows'])
        label('MALE', ncols)
        table(section['headers'], section['male_rows'])

    widths = [5, 14, 18, 18, 6, 6, 16, 14, 14, 12, 14, 22, 5, 26]
    for ci, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f'UniFAST_Scholars_{ay.replace("-", "_")}_{semester.replace(" ", "_")}.xlsx'
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@_vpsea_required
def vpsea_announcements(request):
    from .models import Announcement
    if request.method == 'POST':
        Announcement.objects.create(
            title=request.POST.get('title'),
            body=request.POST.get('body'),
            published_by=request.user,
        )
        return redirect('/vpsea/announcements/')
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'vpsea/announcements.html', {'announcements': announcements})


@_vpsea_required
def vpsea_reports(request):
    """Preview of the BiPSU scholars masterlist.

    Built from the same context that renders the Word document, so what the page
    shows and what downloads can never drift apart.
    """
    import os
    from .models import SystemSettings
    from . import masterlist_report

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    context, summary = masterlist_report.build_context()

    sections = []
    for entry in summary:
        slot = context[entry['slot']]
        gendered = entry['layout'] == 'gendered'
        headers = entry['headers']

        def cells(rows):
            # Resolved against this table's own headings, so the preview shows
            # exactly the columns the document will — no more, no fewer.
            return [masterlist_report.cells_for(r, headers) for r in rows]

        sections.append((
            entry['heading'],
            headers,
            cells(slot['female'] if gendered else slot['students']),
            cells(slot['male']) if gendered else [],
            gendered,
            entry['key'].lower(),
        ))

    return render(request, 'vpsea/reports.html', {
        'sections': sections,
        'semester': parsed['semester'],
        'ay': parsed['sy'],
        'grand_total': sum(e['total'] for e in summary),
        'summary': summary,
        'template_available': os.path.exists(masterlist_report.TEMPLATE_PATH),
        'error': request.GET.get('error'),
    })


@_vpsea_required
@xframe_options_exempt
def vpsea_report_preview_pdf(request):
    from reportlab.lib.pagesizes import landscape, legal
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from io import BytesIO
    from django.http import HttpResponse
    from .models import Application, AffirmativeStaffApplication, SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    semester = settings_obj.active_semester
    ay = settings_obj.academic_year

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(legal),
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.7*inch, bottomMargin=0.5*inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Normal'], fontSize=13, alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=2)
    sub_style   = ParagraphStyle('sub',   parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, spaceAfter=2)
    sec_style   = ParagraphStyle('sec',   parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=4, spaceBefore=8)
    lbl_style   = ParagraphStyle('lbl',   parent=styles['Normal'], fontSize=9,  alignment=TA_LEFT,   fontName='Helvetica-Bold')
    cell_style  = ParagraphStyle('cell',  parent=styles['Normal'], fontSize=7)

    HDR_BG  = colors.HexColor('#D9E1F2')
    SEC_BG  = colors.HexColor('#BDD7EE')
    TITLE_BG = colors.HexColor('#1F4E79')
    TITLE_FG = colors.white

    def _split(full):
        p = full.strip().split()
        if not p: return '', '', ''
        if len(p) == 1: return p[0], '', ''
        if len(p) == 2: return p[-1], p[0], ''
        mi = p[1][0] + '.' if len(p) > 2 else ''
        return p[-1], p[0], mi

    def _addr(profile):
        return profile.barangay, profile.municipality, profile.province

    def make_table(headers, rows):
        data = [headers] + (rows if rows else [['—'] * len(headers)])
        col_w = (landscape(legal)[0] - inch) / len(headers)
        t = Table(data, colWidths=[col_w] * len(headers), repeatRows=1)
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), HDR_BG),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 7),
            ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            ('GRID',       (0,0), (-1,-1), 0.4, colors.black),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F5F7FF')]),
        ])
        t.setStyle(style)
        return t

    story = []
    story.append(Paragraph('Republic of the Philippines', sub_style))
    story.append(Paragraph('BILIRAN PROVINCE STATE UNIVERSITY — Naval, Biliran', title_style))
    story.append(Paragraph(f'LIST OF SCHOLARS FOR {semester} SY: {ay}', title_style))
    story.append(Spacer(1, 8))

    # ── ACADEMIC ──────────────────────────────────────────────────────────────
    academic = list(Application.objects.filter(
        status='Approved', scholarship__type='Academic'
    ).select_related('student__user').order_by('student__user__last_name'))
    females_a = [a for a in academic if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
    males_a   = [a for a in academic if a not in females_a]

    hdrs_acad = ['NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','COURSE','YR.','GWA','%','SCHOLARSHIP']

    def acad_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            pct = 'Univ. Scholar' if p.gwa <= 1.29 else ('College Scholar' if p.gwa <= 1.50 else '')
            rows.append([i, u.last_name, u.first_name, '', p.gender or '', p.barangay, p.municipality, p.province, p.course, p.year_level, p.gwa, pct, 'ACADEMIC'])
        return rows

    story.append(Paragraph(f'ACADEMIC (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_acad, acad_rows(females_a)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_acad, acad_rows(males_a)))
    story.append(Spacer(1, 10))

    # ── BiPSU STAFF ─────────────────────────────────────────────────────────────
    staff = list(AffirmativeStaffApplication.objects.filter(status='Approved', qualified_for='Staff').order_by('full_name'))
    hdrs_staff = ['NO.','LAST NAME','FIRST NAME','M.I.','SEX','COURSE','YEAR LEVEL','STUDENT NO.','%','SCHOLARSHIP PROGRAM']
    staff_rows = []
    for i, app in enumerate(staff, 1):
        last, first, mi = _split(app.full_name)
        staff_rows.append([i, last, first, mi, app.gender or '', app.course, app.year_level, app.student_id or '', '100' if app.is_nsu_staff else '75', 'BiPSU STAFF'])
    story.append(Paragraph(f'BiPSU STAFF (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(make_table(hdrs_staff, staff_rows))
    story.append(Spacer(1, 10))

    # ── AFFIRMATIVE ───────────────────────────────────────────────────────────
    affirmative = list(AffirmativeStaffApplication.objects.filter(status='Approved', qualified_for='Affirmative').order_by('full_name'))
    aff_f = [a for a in affirmative if a.gender and a.gender.upper() in ('F','FEMALE')]
    aff_m = [a for a in affirmative if a not in aff_f]
    hdrs_aff = ['NO.','AWARD NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','CONG. DIST.','COURSE','YR.','SCHOLARSHIP PROGRAM']

    def aff_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            last, first, mi = _split(app.full_name)
            rows.append([i, '', last, first, mi, app.gender or '', app.barangay, app.municipality, app.province, '', app.course, app.year_level, 'Affirmative Action'])
        return rows

    story.append(Paragraph(f'AN WARAY (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_aff, aff_rows(aff_f)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_aff, aff_rows(aff_m)))
    story.append(Spacer(1, 10))

    # ── CHED ──────────────────────────────────────────────────────────────────
    ched_all = list(Application.objects.filter(status='Approved', scholarship__type='CHED').select_related('student__user','scholarship').order_by('student__user__last_name'))
    ched_full, ched_half = split_ched(ched_all)
    hdrs_ched = ['NO.','AWARD NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','CONG. DIST.','COURSE','YR.','SCHOLARSHIP PROGRAM']

    def ched_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            rows.append([i, app.award_number, u.last_name, u.first_name, '', p.gender or '', p.barangay, p.municipality, p.province, app.congress_district, p.course, p.year_level, app.scholarship.name])
        return rows

    for title, block in [('FULL MERIT/ FULL SCHOLAR (*)', ched_full), ('HALF MERIT/ PARTIAL SCHOLAR (*)', ched_half)]:
        story.append(Paragraph(f'{title} — {semester} SY: {ay}', sec_style))
        bf = [a for a in block if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
        bm = [a for a in block if a not in bf]
        story.append(Paragraph('FEMALE', lbl_style))
        story.append(make_table(hdrs_ched, ched_rows(bf)))
        story.append(Paragraph('MALE', lbl_style))
        story.append(make_table(hdrs_ched, ched_rows(bm)))
        story.append(Spacer(1, 10))

    # ── DOST ──────────────────────────────────────────────────────────────────
    dost_all = list(Application.objects.filter(status='Approved', scholarship__type='DOST').select_related('student__user','scholarship').order_by('student__user__last_name'))
    dost_f = [a for a in dost_all if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
    dost_m = [a for a in dost_all if a not in dost_f]
    story.append(Paragraph(f'DOST (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_ched, ched_rows(dost_f)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_ched, ched_rows(dost_m)))
    story.append(Spacer(1, 10))

    # ── GSIS ──────────────────────────────────────────────────────────────────
    gsis_all = list(Application.objects.filter(status='Approved', scholarship__type='GSIS').select_related('student__user','scholarship').order_by('student__user__last_name'))
    hdrs_gsis = ['NO.','LAST NAME','FIRST NAME','M.I.','SEX','BRGY./ST.','MUN.','PROV.','CONG. DIST.','COURSE','YR.','SCHOLARSHIP PROGRAM']

    def gsis_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            rows.append([i, u.last_name, u.first_name, '', p.gender or '', p.barangay, p.municipality, p.province, app.congress_district, p.course, p.year_level, app.scholarship.name])
        return rows

    gsis_f = [a for a in gsis_all if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
    gsis_m = [a for a in gsis_all if a not in gsis_f]
    story.append(Paragraph(f'GSIS (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_gsis, gsis_rows(gsis_f)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_gsis, gsis_rows(gsis_m)))
    story.append(Spacer(1, 10))

    # ── TDP/TES ───────────────────────────────────────────────────────────────
    tes_all = list(Application.objects.filter(status='Approved', scholarship__type='TDP').select_related('student__user','scholarship').order_by('student__user__last_name'))
    tes_f = [a for a in tes_all if a.student.gender and a.student.gender.upper() in ('F','FEMALE')]
    tes_m = [a for a in tes_all if a not in tes_f]
    story.append(Paragraph(f'TERTIARY EDUCATION SUBSIDY - TES (*) — {semester} SY: {ay}', sec_style))
    story.append(Paragraph('FEMALE', lbl_style))
    story.append(make_table(hdrs_ched, ched_rows(tes_f)))
    story.append(Paragraph('MALE', lbl_style))
    story.append(make_table(hdrs_ched, ched_rows(tes_m)))

    doc.build(story)
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="masterlist_preview.pdf"'
    return response


@_vpsea_required
def vpsea_report_download(request):
    """The BiPSU scholars masterlist as the office's own Word document."""
    from .models import SystemSettings
    from . import masterlist_report

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    try:
        buf, _summary = masterlist_report.build_document(parsed['sy'], parsed['semester'])
    except FileNotFoundError as exc:
        from urllib.parse import quote
        return redirect(f'/vpsea/reports/?error={quote(str(exc))}')

    label = settings_obj.academic_year.replace('-', '_')
    filename = f'BiPSU_List_of_Scholars_{label}.docx'
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

    # — Page layout: landscape, legal-ish wide ————————————————
    section = doc.sections[0]
    section.orientation = 1  # LANDSCAPE
    section.page_width = Inches(13.0)
    section.page_height = Inches(8.5)
    section.left_margin = Inches(0.5)
    section.right_margin = Inches(0.5)
    section.top_margin = Inches(0.9)
    section.bottom_margin = Inches(0.4)

    # — Helpers ————————————————————————————————
    def add_heading(text, bold=False, size=11, align=WD_ALIGN_PARAGRAPH.CENTER):
        p = doc.add_paragraph()
        p.alignment = align
        run = p.add_run(text)
        run.bold = bold
        run.font.size = Pt(size)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        return p

    def add_blank():
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)

    def set_cell_border(cell):
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        for edge in ('top', 'left', 'bottom', 'right'):
            tag = OxmlElement(f'w:{edge}')
            tag.set(qn('w:val'), 'single')
            tag.set(qn('w:sz'), '4')
            tag.set(qn('w:space'), '0')
            tag.set(qn('w:color'), '000000')
            tcPr.append(tag)

    def style_header_row(row, bold=True, bg='D9E1F2'):
        for cell in row.cells:
            set_cell_border(cell)
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'), bg)
            tcPr.append(shd)
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in para.runs:
                    run.bold = bold
                    run.font.size = Pt(8)

    def style_data_row(row):
        for cell in row.cells:
            set_cell_border(cell)
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(8)

    def add_scholar_table(headers, sub_headers, rows_data):
        ncols = len(headers)
        table = doc.add_table(rows=0, cols=ncols)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        # Header row 1
        hrow1 = table.add_row()
        for i, h in enumerate(headers):
            hrow1.cells[i].text = h
        style_header_row(hrow1)
        # Header row 2 (sub-headers)
        if sub_headers:
            hrow2 = table.add_row()
            for i, h in enumerate(sub_headers):
                hrow2.cells[i].text = h
            style_header_row(hrow2)
        # Data rows
        for row_vals in rows_data:
            drow = table.add_row()
            for i, val in enumerate(row_vals):
                drow.cells[i].text = str(val) if val is not None else ''
            style_data_row(drow)
        return table

    def _split_name(full_name):
        parts = full_name.strip().split()
        if len(parts) == 0: return ('', '', '')
        if len(parts) == 1: return (parts[0], '', '')
        if len(parts) == 2: return (parts[-1], parts[0], '')
        last = parts[-1]
        first = parts[0]
        middle = ' '.join(parts[1:-1])
        mi = middle[0] + '.' if middle else ''
        return (last, first, mi)

    def _name_parts(user):
        return (user.last_name or '', user.first_name or '', '')

    # — Document header ————————————————————————————
    add_heading('Republic of the Philippines', bold=False, size=11)
    add_heading('BILIRAN PROVINCE STATE UNIVERSITY', bold=True, size=11)
    add_heading('Naval, Biliran', bold=False, size=11)
    add_blank()
    add_heading(f'LIST OF SCHOLARS FOR {sem_label}', bold=True, size=16)
    add_blank()

    # — ACADEMIC ———————————————————————————————
    academic = Application.objects.filter(
        status='Approved', scholarship__type='Academic'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    females = [a for a in academic if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    males   = [a for a in academic if a not in females]

    add_heading('ACADEMIC (@)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    headers_acad = ['NO.', 'NAME', 'NAME', 'NAME', 'SEX', 'ADDRESS', 'ADDRESS', 'ADDRESS', 'COURSE', 'YR.', 'GWA', '%', 'SCHOLARSHIP PROGRAM']
    sub_acad     = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'COURSE', 'YR.', 'GWA', '%', 'SCHOLARSHIP PROGRAM']

    def acad_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            addr = p.address or ''
            parts = [x.strip() for x in addr.split(',')]
            brgy = parts[0] if len(parts) > 0 else ''
            mun  = parts[1] if len(parts) > 1 else ''
            prov = parts[2] if len(parts) > 2 else ''
            pct = 'University Scholar' if p.gwa <= 1.29 else ('College Scholars' if p.gwa <= 1.50 else '')
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, p.course, p.year_level, p.gwa, pct, 'ACADEMIC'])
        return rows

    p_label = doc.add_paragraph('FEMALE')
    p_label.paragraph_format.space_before = Pt(0)
    p_label.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_acad, sub_acad, acad_rows(females))
    add_blank()
    p_label2 = doc.add_paragraph('MALE')
    p_label2.paragraph_format.space_before = Pt(0)
    p_label2.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_acad, sub_acad, acad_rows(males))
    add_blank()

    # — BiPSU STAFF ———————————————————————————————
    staff = AffirmativeStaffApplication.objects.filter(
        status='Approved', qualified_for='Staff'
    ).order_by('full_name')

    add_heading('BiPSU STAFF (@)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    headers_staff = ['NO. ', 'NAME ', 'NAME ', 'NAME ', 'SEX', 'COURSE ', 'YEAR LEVEL ', 'STUDENT ', '% ', 'SCHOLARSHIP ']
    sub_staff     = ['NO. ', 'LAST NAME ', 'FIRST NAME ', 'M.I. ', 'SEX', 'COURSE ', 'YEAR LEVEL ', 'NUMBER ', '% ', 'PROGRAM ']
    staff_rows = []
    for i, app in enumerate(staff, 1):
        last, first, mi = _split_name(app.full_name)
        pct = '100' if app.is_nsu_staff else '75'
        staff_rows.append([i, last, first, mi, app.gender or '', app.course, app.year_level, app.student_id or '', pct, 'BiPSU STAFF SCHOLARSHIP'])
    add_scholar_table(headers_staff, sub_staff, staff_rows)
    add_blank()

    # — AFFIRMATIVE (AN WARAY) ————————————————————————
    affirmative = AffirmativeStaffApplication.objects.filter(
        status='Approved', qualified_for='Affirmative'
    ).order_by('full_name')

    aff_females = [a for a in affirmative if a.gender and a.gender.upper() in ('F', 'FEMALE')]
    aff_males   = [a for a in affirmative if a not in aff_females]

    add_heading('AN WARAY (*)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    headers_aff = ['NO.', 'AWARD NUMBER', 'NAME', 'NAME', 'NAME', 'SEX', 'ADDRESS', 'ADDRESS', 'ADDRESS', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    sub_aff     = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    def aff_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            last, first, mi = _split_name(app.full_name)
            addr = app.address or ''
            parts = [x.strip() for x in addr.split(',')]
            brgy = parts[0] if len(parts) > 0 else ''
            mun  = parts[1] if len(parts) > 1 else ''
            prov = parts[2] if len(parts) > 2 else ''
            rows.append([i, '', last, first, mi, app.gender or '', brgy, mun, prov, '', app.course, app.year_level, 'Affirmative Action Scholarship'])
        return rows

    p_f = doc.add_paragraph('FEMALE')
    p_f.paragraph_format.space_before = Pt(0)
    p_f.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_aff, sub_aff, aff_rows(aff_females))
    add_blank()
    p_m = doc.add_paragraph('MALE')
    p_m.paragraph_format.space_before = Pt(0)
    p_m.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_aff, sub_aff, aff_rows(aff_males))
    add_blank()

    # — CHED (FULL MERIT / HALF MERIT) ————————————————————
    ched_all = Application.objects.filter(
        status='Approved', scholarship__type='CHED'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    ched_full, ched_half = split_ched(ched_all)

    headers_ched = ['NO.', 'AWARD NUMBER', 'NAME', 'NAME', 'NAME', 'SEX', 'ADDRESS', 'ADDRESS', 'ADDRESS', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    sub_ched     = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    def ched_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            addr = p.address or ''
            parts = [x.strip() for x in addr.split(',')]
            brgy = parts[0] if len(parts) > 0 else ''
            mun  = parts[1] if len(parts) > 1 else ''
            prov = parts[2] if len(parts) > 2 else ''
            award = app.award_number
            cong  = app.congress_district
            rows.append([i, award, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    for block_title, block_apps in [('FULL MERIT/ FULL SCHOLAR (*)', ched_full), ('HALF MERIT/ PARTIAL SCHOLAR (*)', ched_half)]:
        add_heading(block_title, bold=True, size=11)
        add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
        add_heading(f'{semester} SY: {ay}', bold=False, size=11)
        add_blank()
        ched_f = [a for a in block_apps if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
        ched_m = [a for a in block_apps if a not in ched_f]
        pf = doc.add_paragraph('FEMALE')
        pf.paragraph_format.space_before = Pt(0)
        pf.paragraph_format.space_after = Pt(0)
        add_scholar_table(headers_ched, sub_ched, ched_rows(ched_f))
        add_blank()
        pm = doc.add_paragraph('MALE')
        pm.paragraph_format.space_before = Pt(0)
        pm.paragraph_format.space_after = Pt(0)
        add_scholar_table(headers_ched, sub_ched, ched_rows(ched_m))
        add_blank()

    # — DOST —————————————————————————————————
    dost_all = Application.objects.filter(
        status='Approved', scholarship__type='DOST'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    add_heading('DOST (*)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    dost_f = [a for a in dost_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    dost_m = [a for a in dost_all if a not in dost_f]
    pf = doc.add_paragraph('FEMALE')
    pf.paragraph_format.space_before = Pt(0)
    pf.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_ched, sub_ched, ched_rows(dost_f))
    add_blank()
    pm = doc.add_paragraph('MALE')
    pm.paragraph_format.space_before = Pt(0)
    pm.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_ched, sub_ched, ched_rows(dost_m))
    add_blank()

    # — GSIS —————————————————————————————————
    gsis_all = Application.objects.filter(
        status='Approved', scholarship__type='GSIS'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    add_heading('GSIS (*)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    headers_gsis = ['NO.', 'NAME', 'NAME', 'NAME', 'SEX', 'ADDRESS', 'ADDRESS', 'ADDRESS', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    sub_gsis     = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    def gsis_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            addr = p.address or ''
            parts = [x.strip() for x in addr.split(',')]
            brgy = parts[0] if len(parts) > 0 else ''
            mun  = parts[1] if len(parts) > 1 else ''
            prov = parts[2] if len(parts) > 2 else ''
            cong = app.congress_district
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    gsis_f = [a for a in gsis_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    gsis_m = [a for a in gsis_all if a not in gsis_f]
    pf = doc.add_paragraph('FEMALE')
    pf.paragraph_format.space_before = Pt(0)
    pf.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_gsis, sub_gsis, gsis_rows(gsis_f))
    add_blank()
    pm = doc.add_paragraph('MALE')
    pm.paragraph_format.space_before = Pt(0)
    pm.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_gsis, sub_gsis, gsis_rows(gsis_m))
    add_blank()

    # — TES (TDP) ———————————————————————————————
    tes_all = Application.objects.filter(
        status='Approved', scholarship__type='TDP'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')

    add_heading('TERTIARY EDUCATION SUBSIDY -TES (*)', bold=True, size=11)
    add_heading('SCHOLARSHIP GRANT', bold=False, size=11)
    add_heading(f'{semester} SY: {ay}', bold=False, size=11)
    add_blank()

    tes_f = [a for a in tes_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    tes_m = [a for a in tes_all if a not in tes_f]
    pf = doc.add_paragraph('FEMALE')
    pf.paragraph_format.space_before = Pt(0)
    pf.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_ched, sub_ched, ched_rows(tes_f))
    add_blank()
    pm = doc.add_paragraph('MALE')
    pm.paragraph_format.space_before = Pt(0)
    pm.paragraph_format.space_after = Pt(0)
    add_scholar_table(headers_ched, sub_ched, ched_rows(tes_m))
    add_blank()

    # — Page footer with signatories (appears on every page) —————————
    footer = section.footer
    footer.is_linked_to_previous = False
    # Clear default empty paragraph
    for para in footer.paragraphs:
        p_elem = para._p
        p_elem.getparent().remove(p_elem)

    footer_table = footer.add_table(rows=2, cols=4, width=Inches(12.0))
    footer_table.style = 'Table Grid'

    sig_labels = [
        ('Prepared by:', 'Noted:', 'Recommending approval:', 'Approved:'),
        (
            'MARICEL S. SAULAN\nScholarship in charge',
            'NORMA M. DUALLO, Ph.D.TM\nSDSO Director',
            'ERWIN G. SALVATIERRA, Ph. D.\nVP for Extension Services,\nStudent and External Affairs',
            'VICTOR C. CAÃ‘EZO, JR., Ed. D.\nUniversity President',
        ),
    ]
    for ri, row_vals in enumerate(sig_labels):
        for ci, val in enumerate(row_vals):
            cell = footer_table.rows[ri].cells[ci]
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # remove cell borders
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            for edge in ('top', 'left', 'bottom', 'right'):
                tag = OxmlElement(f'w:{edge}')
                tag.set(qn('w:val'), 'none')
                tcPr.append(tag)
            if ri == 0:
                run = para.add_run(val)
                run.bold = True
                run.font.size = Pt(8)
            else:
                lines = val.split('\n')
                r1 = para.add_run(lines[0])
                r1.bold = True
                r1.font.size = Pt(8)
                for line in lines[1:]:
                    para.add_run('\n' + line).font.size = Pt(8)

    # — Save & return —————————————————————————————
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    filename = f'Scholarship_Report_{ay.replace("-","_")}_{semester.replace(" ","_")}.docx'
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@_vpsea_required
def vpsea_report_download_excel(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from django.http import HttpResponse
    from .models import Application, AffirmativeStaffApplication, SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    semester = settings_obj.active_semester
    ay = settings_obj.academic_year

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Scholars'

    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    header_font = Font(bold=True, size=9)
    header_fill = PatternFill('solid', fgColor='D9E1F2')
    section_fill = PatternFill('solid', fgColor='BDD7EE')
    title_fill = PatternFill('solid', fgColor='1F4E79')
    title_font = Font(bold=True, size=11, color='FFFFFF')

    current_row = [1]  # mutable so nested helpers can update it

    def write_title(text, ncols):
        r = current_row[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = center
        cell.border = border
        ws.row_dimensions[r].height = 18
        current_row[0] += 1

    def write_section(text, ncols):
        r = current_row[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font = Font(bold=True, size=10)
        cell.fill = section_fill
        cell.alignment = center
        cell.border = border
        current_row[0] += 1

    def write_gender_label(text, ncols):
        r = current_row[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font = Font(bold=True, size=9)
        cell.alignment = Alignment(horizontal='left', vertical='center')
        current_row[0] += 1

    def write_headers(headers):
        r = current_row[0]
        for ci, h in enumerate(headers, 1):
            cell = ws.cell(row=r, column=ci, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = center
        current_row[0] += 1

    def write_rows(rows_data):
        for row_vals in rows_data:
            r = current_row[0]
            for ci, val in enumerate(row_vals, 1):
                cell = ws.cell(row=r, column=ci, value=val)
                cell.border = border
                cell.alignment = Alignment(vertical='center', wrap_text=True)
                cell.font = Font(size=9)
            current_row[0] += 1

    def blank_row():
        current_row[0] += 1

    def _split_name(full_name):
        parts = full_name.strip().split()
        if len(parts) == 0: return ('', '', '')
        if len(parts) == 1: return (parts[0], '', '')
        if len(parts) == 2: return (parts[-1], parts[0], '')
        last = parts[-1]; first = parts[0]
        middle = ' '.join(parts[1:-1])
        return (last, first, middle[0] + '.' if middle else '')

    def _name_parts(user):
        return (user.last_name or '', user.first_name or '', '')

    def addr_parts(addr):
        parts = [x.strip() for x in (addr or '').split(',')]
        return (parts[0] if len(parts) > 0 else '',
                parts[1] if len(parts) > 1 else '',
                parts[2] if len(parts) > 2 else '')

    MAX_COLS = 13  # widest table

    # — Document title ————————————————————————————
    write_title('Republic of the Philippines', MAX_COLS)
    write_title('BILIRAN PROVINCE STATE UNIVERSITY — Naval, Biliran', MAX_COLS)
    write_title(f'LIST OF SCHOLARS FOR {semester} SY: {ay}', MAX_COLS)
    blank_row()

    # — ACADEMIC ———————————————————————————————
    academic = list(Application.objects.filter(
        status='Approved', scholarship__type='Academic'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    females_a = [a for a in academic if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    males_a   = [a for a in academic if a not in females_a]

    headers_acad = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'COURSE', 'YR.', 'GWA', '%', 'SCHOLARSHIP PROGRAM']
    write_section(f'ACADEMIC (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_acad))

    def acad_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            brgy, mun, prov = addr_parts(p.address)
            pct = 'University Scholar' if p.gwa <= 1.29 else ('College Scholars' if p.gwa <= 1.50 else '')
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, p.course, p.year_level, p.gwa, pct, 'ACADEMIC'])
        return rows

    write_gender_label('FEMALE', len(headers_acad))
    write_headers(headers_acad)
    write_rows(acad_rows(females_a))
    write_gender_label('MALE', len(headers_acad))
    write_headers(headers_acad)
    write_rows(acad_rows(males_a))
    blank_row()

    # — BiPSU STAFF ———————————————————————————————
    staff = list(AffirmativeStaffApplication.objects.filter(
        status='Approved', qualified_for='Staff'
    ).order_by('full_name'))
    headers_staff = ['NO.', 'LAST NAME', 'FIRST NAME', 'M.I.', 'SEX', 'COURSE', 'YEAR LEVEL', 'STUDENT NUMBER', '%', 'SCHOLARSHIP PROGRAM']
    write_section(f'BiPSU STAFF (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_staff))
    write_headers(headers_staff)
    staff_rows = []
    for i, app in enumerate(staff, 1):
        last, first, mi = _split_name(app.full_name)
        pct = '100' if app.is_nsu_staff else '75'
        staff_rows.append([i, last, first, mi, app.gender or '', app.course, app.year_level, app.student_id or '', pct, 'BiPSU STAFF SCHOLARSHIP'])
    write_rows(staff_rows)
    blank_row()

    # — AFFIRMATIVE ——————————————————————————————
    affirmative = list(AffirmativeStaffApplication.objects.filter(
        status='Approved', qualified_for='Affirmative'
    ).order_by('full_name'))
    aff_females = [a for a in affirmative if a.gender and a.gender.upper() in ('F', 'FEMALE')]
    aff_males   = [a for a in affirmative if a not in aff_females]
    headers_aff = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    write_section(f'AN WARAY (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_aff))

    def aff_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            last, first, mi = _split_name(app.full_name)
            brgy, mun, prov = addr_parts(app.address)
            rows.append([i, '', last, first, mi, app.gender or '', brgy, mun, prov, '', app.course, app.year_level, 'Affirmative Action Scholarship'])
        return rows

    write_gender_label('FEMALE', len(headers_aff))
    write_headers(headers_aff)
    write_rows(aff_rows(aff_females))
    write_gender_label('MALE', len(headers_aff))
    write_headers(headers_aff)
    write_rows(aff_rows(aff_males))
    blank_row()

    # — CHED —————————————————————————————————
    ched_all = list(Application.objects.filter(
        status='Approved', scholarship__type='CHED'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    ched_full, ched_half = split_ched(ched_all)
    headers_ched = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    def ched_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            brgy, mun, prov = addr_parts(p.address)
            award = app.award_number
            cong  = app.congress_district
            rows.append([i, award, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    for block_title, block_apps in [('FULL MERIT/ FULL SCHOLAR (*)', ched_full), ('HALF MERIT/ PARTIAL SCHOLAR (*)', ched_half)]:
        write_section(f'{block_title} SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
        bf = [a for a in block_apps if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
        bm = [a for a in block_apps if a not in bf]
        write_gender_label('FEMALE', len(headers_ched))
        write_headers(headers_ched)
        write_rows(ched_rows(bf))
        write_gender_label('MALE', len(headers_ched))
        write_headers(headers_ched)
        write_rows(ched_rows(bm))
        blank_row()

    # — DOST —————————————————————————————————
    dost_all = list(Application.objects.filter(
        status='Approved', scholarship__type='DOST'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    write_section(f'DOST (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
    dost_f = [a for a in dost_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    dost_m = [a for a in dost_all if a not in dost_f]
    write_gender_label('FEMALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(dost_f))
    write_gender_label('MALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(dost_m))
    blank_row()

    # — GSIS —————————————————————————————————
    gsis_all = list(Application.objects.filter(
        status='Approved', scholarship__type='GSIS'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    headers_gsis = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    write_section(f'GSIS (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_gsis))

    def gsis_rows(apps):
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            brgy, mun, prov = addr_parts(p.address)
            cong = app.congress_district
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    gsis_f = [a for a in gsis_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    gsis_m = [a for a in gsis_all if a not in gsis_f]
    write_gender_label('FEMALE', len(headers_gsis))
    write_headers(headers_gsis)
    write_rows(gsis_rows(gsis_f))
    write_gender_label('MALE', len(headers_gsis))
    write_headers(headers_gsis)
    write_rows(gsis_rows(gsis_m))
    blank_row()

    # — TES (TDP) ———————————————————————————————
    tes_all = list(Application.objects.filter(
        status='Approved', scholarship__type='TDP'
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name'))
    write_section(f'TERTIARY EDUCATION SUBSIDY -TES (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
    tes_f = [a for a in tes_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    tes_m = [a for a in tes_all if a not in tes_f]
    write_gender_label('FEMALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(tes_f))
    write_gender_label('MALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(tes_m))
    blank_row()
    blank_row()

    # — Page footer with signatories (appears on every printed page) —————
    footer_text = (
        'Prepared by:\t\t\t\t\tNoted:\t\t\t\t\t\tRecommending approval:\t\t\t\t\t\tApproved:\n'
        'MARICEL S. SAULAN\t\t\t\tNORMA M. DUALLO, Ph.D.TM\t\t\tERWIN G. SALVATIERRA, Ph. D.\t\t\tVICTOR C. CAÃ‘EZO, JR., Ed. D.\n'
        'Scholarship in charge\t\t\t\tSDSO Director\t\t\t\t\tVP for Extension Services, Student and External Affairs\t\tUniversity President'
    )
    ws.oddFooter.center.text = footer_text
    ws.oddFooter.center.size = 8
    ws.evenFooter.center.text = footer_text
    ws.evenFooter.center.size = 8

    # — Auto-fit columns (skip MergedCell objects) ——————————————
    from openpyxl.utils import get_column_letter
    for col_idx in range(1, ws.max_column + 1):
        max_len = 0
        col_letter = get_column_letter(col_idx)
        for row_idx in range(1, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 3, 35)

    # — Save & return —————————————————————————————
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f'Scholarship_Report_{ay.replace("-","_")}_{semester.replace(" ","_")}.xlsx'
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@_vpsea_required
def vpsea_accounts(request):
    """Verification queue for accounts that registered themselves.

    Nobody who signs up on the public form can sign in until an officer decides
    here. The decision writes the message the person reads on the login page,
    which is the only channel that reaches someone who cannot get in yet — so
    a rejection has to say why.
    """
    from .models import ActivityLog, Notification, StaffProfile, StudentProfile

    if request.method == 'POST':
        account = User.objects.filter(
            id=request.POST.get('user_id'), role__in=('student', 'nsu_staff'),
        ).first()
        if not account:
            return redirect('/vpsea/accounts/?error=Account+not+found')

        action = request.POST.get('action')
        message = request.POST.get('message', '').strip()
        if action == 'reject' and not message:
            return redirect('/vpsea/accounts/?error=A+reason+is+required+when+rejecting'
                            '+—+it+is+what+the+person+reads+when+they+try+to+sign+in')
        if action not in ('approve', 'reject'):
            return redirect('/vpsea/accounts/?error=Unknown+action')

        status = 'approved' if action == 'approve' else 'rejected'
        account.decide_verification(status, message, request.user)

        # A verified student finds this waiting in their portal. Staff
        # notifications hang off StudentProfile, which staff do not have, so
        # for them the login page is the whole of it.
        profile = StudentProfile.objects.filter(user=account).first()
        if profile and status == 'approved':
            Notification.objects.create(
                student=profile, type='success',
                title='Account verified',
                body=account.verification_note,
            )
        ActivityLog.objects.create(
            user=request.user,
            action=(f'Account {status}: {account.get_full_name() or account.email} '
                    f'({account.get_role_display()}) — {account.verification_note}'),
        )
        return redirect(f'/vpsea/accounts/?{action}d=1')

    pending = list(User.objects.filter(
        verification_status='pending', role__in=('student', 'nsu_staff'),
    ).order_by('date_joined'))
    decided = list(User.objects.filter(
        verification_status__in=('approved', 'rejected'),
        role__in=('student', 'nsu_staff'), verified_at__isnull=False,
    ).select_related('verified_by').order_by('-verified_at')[:25])

    # What each account claimed about itself, so the officer can check it
    # against their own records without opening another page.
    students = {p.user_id: p for p in StudentProfile.objects.filter(
        user__in=pending + decided)}
    staff = {p.user_id: p for p in StaffProfile.objects.filter(
        user__in=pending + decided)}
    for account in pending + decided:
        account.student_profile = students.get(account.id)
        account.employee_profile = staff.get(account.id)

    return render(request, 'vpsea/accounts.html', {
        'active': 'accounts',
        'pending': pending,
        'decided': decided,
        'error': request.GET.get('error', ''),
        'approved': request.GET.get('approved'),
        'rejected': request.GET.get('rejected'),
    })


@_vpsea_required
def vpsea_students(request):
    from .models import StudentProfile, Application, Scholarship, SystemSettings
    from django.db.models import Q

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    # academic_year holds the '<yy>-<sem>' label, e.g. '26-1'. Expanding it is
    # what the page means to show: it was printing 'A.Y. 26-1' in the subtitle
    # and, worse, int('26-1'.split('-')[0]) == 26 was being used as a calendar
    # year, so the approved-scholar filter matched nothing at all.
    active_label = settings_obj.academic_year
    parsed = SystemSettings.parse_label(active_label)
    current_sy = parsed['sy']                    # e.g. '2026-2027'
    current_sem = parsed['semester']

    q = request.GET.get('q', '').strip()
    stype = request.GET.get('stype', '').strip()

    scholarship_types = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']

    # Base: only students with an Approved award for the active term, matched
    # on the term column rather than guessed from the submission date.
    students = StudentProfile.objects.select_related('user').order_by('user__last_name')
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
            from .models import AffirmativeStaffApplication
            aff_emails = AffirmativeStaffApplication.objects.filter(
                qualified_for=stype, status='Approved'
            ).values_list('email', flat=True)
            students = students.filter(user__email__in=aff_emails)
        else:
            students = students.filter(
                applications__scholarship__type=stype
            ).distinct()

    # Students with NO approved application at all — shown in the second tab.
    # This is a simple anti-join: every StudentProfile whose pk is not in the
    # set of profiles that have at least one Approved application.
    approved_pks = Application.objects.filter(
        status='Approved'
    ).values_list('student_id', flat=True).distinct()

    no_scholarship_qs = (
        StudentProfile.objects
        .select_related('user')
        .exclude(pk__in=approved_pks)
        .order_by('user__last_name', 'user__first_name')
    )
    if q:
        no_scholarship_qs = no_scholarship_qs.filter(
            Q(user__last_name__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(student_id__icontains=q)
        )

    tab = request.GET.get('tab', 'scholars')   # 'scholars' | 'no_scholarship'

    return render(request, 'vpsea/students.html', {
        'students': students,
        'no_scholarship_students': no_scholarship_qs,
        'q': q,
        'stype': stype,
        'tab': tab,
        'scholarship_types': scholarship_types,
        'current_sy': current_sy,
        'current_sem': current_sem,
    })


@_vpsea_required
def vpsea_student_add(request):
    from .models import StudentProfile, Scholarship, Application, ApplicationDocument
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
            )
            # Build form_data from all extra fields
            form_data = {
                k: v for k, v in p.items()
                if k not in ('csrfmiddlewaretoken', 'password', 'first_name', 'last_name',
                             'email', 'student_id', 'course', 'year_level', 'gwa',
                             'contact_number', 'barangay', 'municipality', 'province',
                             'date_of_birth', 'gender', 'family_income')
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

    return render(request, 'vpsea/student_form.html', {'errors': errors, 'action': 'Add', 'form_data': request.POST, 'doc_list': _doc_list(),
        # Adding a student creates an application, so the application sections apply.
        'show_application_fields': True,
        'cancel_url': request.GET.get('next') or '/vpsea/students/',

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
        'v_elementary': request.POST.get('elementary', ''),
        'v_highschool': request.POST.get('highschool', ''),
        'v_last_school': request.POST.get('last_school', ''),
        'v_father_name': request.POST.get('father_name', ''),
        'v_father_occupation': request.POST.get('father_occupation', ''),
        'v_mother_name': request.POST.get('mother_name', ''),
        'v_mother_occupation': request.POST.get('mother_occupation', ''),
        'v_semester': request.POST.get('semester', '1st Semester'),
        'v_school_year': request.POST.get('school_year', '2025-2026'),
    })


@_vpsea_required
def vpsea_student_edit(request, pk):
    from .models import StudentProfile, Application, ApplicationDocument
    try:
        profile = StudentProfile.objects.select_related('user').get(pk=pk)
    except StudentProfile.DoesNotExist:
        return redirect('/vpsea/students/')

    # Get the latest Academic application for this student (for form_data + documents)
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
            profile.save()
            # Update form_data on the application
            if app:
                form_data = dict(app.form_data)
                for k, v in p.items():
                    if k not in ('csrfmiddlewaretoken', 'password', 'first_name', 'last_name',
                                 'email', 'student_id', 'middle_name', 'suffix',
                                 'school', 'course', 'year_level', 'gwa',
                                 'contact_number', 'barangay', 'municipality', 'province',
                                 'date_of_birth', 'gender', 'family_income'):
                        form_data[k] = v
                app.form_data = form_data
                app.save()
                # Replace documents if new files uploaded
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
    import json
    return render(request, 'vpsea/student_form.html', {
        'errors': errors, 'action': 'Edit',
        'profile': profile, 'app': app,
        # A student who never applied has no GWA to validate, no term to record
        # and no documents on file. Showing those sections asks the office to
        # fill in an application that does not exist.
        'show_application_fields': app is not None,
        'cancel_url': request.GET.get('next') or '/vpsea/students/',
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
        'v_elementary': fd.get('elementary', afd.get('elementary', '')),
        'v_highschool': fd.get('highschool', afd.get('highschool', '')),
        'v_last_school': fd.get('last_school', afd.get('last_school', '')),
        'v_father_name': fd.get('father_name', afd.get('father_name', '')),
        'v_elementary': fd.get('elementary', profile.elementary or afd.get('elementary', '')),
        'v_highschool': fd.get('highschool', profile.highschool or afd.get('highschool', '')),
        'v_last_school': fd.get('last_school', profile.last_school or afd.get('last_school', '')),
        'v_father_name': fd.get('father_name', profile.father_name or afd.get('father_name', '')),
        'v_father_occupation': fd.get('father_occupation', profile.father_occupation or afd.get('father_occupation', '')),
        'v_mother_name': fd.get('mother_name', profile.mother_name or afd.get('mother_name', '')),
        'v_mother_occupation': fd.get('mother_occupation', profile.mother_occupation or afd.get('mother_occupation', '')),
        'v_semester': fd.get('semester', afd.get('semester', '1st Semester')),
        'v_school_year': fd.get('school_year', afd.get('school_year', '2025-2026')),
        # Extra profile fields for the read-only personal info panel (Edit only)
        'v_civil_status': profile.civil_status,
        'v_citizenship': profile.citizenship,
        'v_household_size': profile.household_size,
        'v_year_first_enrolled': profile.year_first_enrolled,
        'v_is_listahanan': profile.is_listahanan_household,
        'v_is_4ps': profile.is_4ps_beneficiary,
        'v_has_previous_degree': profile.has_previous_degree,
        'v_is_pwd': profile.is_pwd,
        'v_is_athlete': profile.is_athlete,
        'v_is_coconut_farmer': profile.is_coconut_farmer_family,
        'v_has_other_scholarship': profile.has_other_scholarship,
        'v_indigenous_group': profile.indigenous_group,
        'v_shs_gpa': profile.shs_gpa,
        'v_suc_exam_score': profile.suc_exam_score,
        'v_is_tes_beneficiary': profile.is_tes_beneficiary,
    })


def _doc_list():
    return [
        ('doc_certificate_of_grades',   'Certificate Of Grades',   'Official COG from the Registrar for the previous semester.'),
        ('doc_certificate_of_enrollment', 'Certificate Of Enrollment', 'Official COE from the Registrar for the current semester.'),
        ('doc_prospectus',              'Prospectus',              'Program prospectus or subject checklist showing enrolled subjects.'),
        ('doc_id_photo',                'Id Photo',                'Recent 2Ã—2 ID photo with white background.'),
        ('doc_application_form',        'Application Form',        'Signed and accomplished scholarship application form.'),
    ]


@_vpsea_required
def vpsea_student_delete(request, pk):
    from .models import StudentProfile
    if request.method == 'POST':
        try:
            profile = StudentProfile.objects.select_related('user').get(pk=pk)
            profile.user.delete()  # cascades to profile
        except StudentProfile.DoesNotExist:
            pass
        return redirect('/vpsea/students/?deleted=1')
    return redirect('/vpsea/students/')


@_vpsea_required
def vpsea_scholarships(request):
    scholarships = Scholarship.objects.all().order_by('type')
    return render(request, 'vpsea/scholarships.html', {
        'scholarships': scholarships,
        'added': request.GET.get('added'),
        'saved': request.GET.get('saved'),
    })


@_vpsea_required
def vpsea_scholarship_add(request):
    errors = []
    if request.method == 'POST':
        p = request.POST
        name = p.get('name','').strip()
        stype = p.get('type','').strip()
        description = p.get('description','').strip()
        background = p.get('background','').strip()
        eligibility_list = [l.strip() for l in p.get('eligibility_list','').splitlines() if l.strip()]
        benefits = [l.strip() for l in p.get('benefits','').splitlines() if l.strip()]
        if not name: errors.append('Name is required.')
        if not stype: errors.append('Type is required.')
        if not errors:
            Scholarship.objects.create(
                name=name, type=stype, category='application',
                description=description, eligibility='',
                background=background, eligibility_list=eligibility_list,
                benefits=benefits, group=p.get('group','internal'), is_active=True,
            )
            return redirect('/vpsea/scholarships/?added=1')
    return render(request, 'vpsea/scholarship_form.html', {
        'action': 'Add', 'errors': errors, 'form': request.POST,
    })


@_vpsea_required
def vpsea_scholarship_edit(request, pk):
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
        s.eligibility_list = [l.strip() for l in p.get('eligibility_list','').splitlines() if l.strip()]
        s.benefits = [l.strip() for l in p.get('benefits','').splitlines() if l.strip()]
        if not s.name: errors.append('Name is required.')
        if not s.type: errors.append('Type is required.')
        if not errors:
            s.save()
            return redirect('/vpsea/scholarships/?saved=1')
    return render(request, 'vpsea/scholarship_form.html', {
        'action': 'Edit', 'errors': errors, 's': s,
    })


@_vpsea_required
def vpsea_scholarship_toggle(request, pk):
    if request.method == 'POST':
        Scholarship.objects.filter(pk=pk).update(
            is_active=not Scholarship.objects.get(pk=pk).is_active
        )
    return redirect('/vpsea/scholarships/')


@_vpsea_required
def vpsea_ranking(request):
    from .models import AffirmativeRecommendation, SystemSettings

    # TES is UniFAST's programme to award, so its recommender lives in their
    # portal — see unifast_tes_ranking.
    scholarship_type = request.GET.get('type', 'Affirmative')
    scholarship_types = ['Affirmative', 'Staff']
    if scholarship_type not in scholarship_types:
        scholarship_type = 'Affirmative'

    # Recommended tab is Affirmative-only — Staff always stays on applicants
    tab = request.GET.get('tab', 'applicants')   # 'applicants' | 'recommended'
    if scholarship_type == 'Staff':
        tab = 'applicants'

    # ── Passing threshold (can be tweaked via GET param for VPSEA, default 75) ──
    try:
        passing_threshold = float(request.GET.get('passing', 75.0))
    except (TypeError, ValueError):
        passing_threshold = 75.0

    # ── Handle POST: endorse / disqualify a recommendation ───────────────
    if request.method == 'POST':
        rec_id = request.POST.get('rec_id')
        action = request.POST.get('action')
        if rec_id and action in ('endorse', 'disqualify'):
            try:
                rec = AffirmativeRecommendation.objects.get(pk=rec_id)
                rec.status = 'Endorsed' if action == 'endorse' else 'Disqualified'
                rec.notes = request.POST.get('notes', rec.notes)
                rec.save()
            except AffirmativeRecommendation.DoesNotExist:
                pass
        # Re-sync all profiles when admin clicks "Re-evaluate"
        elif action == 'resync':
            AffirmativeRecommendation.evaluate_and_sync(passing_threshold)
        return redirect(f'/vpsea/ranking/?tab={tab}&type={scholarship_type}&passing={passing_threshold}')

    # ── TAB 1: Applicants (AffirmativeStaffApplication) ────────────────────────
    def _aff_score(a):
        s = 0.0
        if a.shs_gpa is not None:
            s += min((a.shs_gpa / 100.0) * 50.0, 50.0)
        if a.suc_exam_score is not None:
            s += min((a.suc_exam_score / 100.0) * 50.0, 50.0)
        return round(s)

    def _staff_score(a):
        return 100 if a.is_nsu_staff else 75

    applicants_qs = AffirmativeStaffApplication.objects.exclude(status='Approved').filter(
        qualified_for=scholarship_type
    )

    def _applicant_rules(a):
        """Return per-rule pass/fail dict for Affirmative applicants."""
        if scholarship_type != 'Affirmative':
            return None
        return {
            'gpa_pass': a.shs_gpa is not None and a.shs_gpa >= passing_threshold,
            'exam_pass': a.suc_exam_score is not None and a.suc_exam_score >= 50.0,
            'not_tes': not a.is_tes_beneficiary,
            'eligible': (
                a.shs_gpa is not None and a.shs_gpa >= passing_threshold and
                a.suc_exam_score is not None and a.suc_exam_score >= 50.0 and
                not a.is_tes_beneficiary
            ),
        }

    raw_score = _aff_score if scholarship_type == 'Affirmative' else _staff_score
    ranked_applicants = sorted(applicants_qs, key=raw_score, reverse=True)
    applicant_rows = [
        {
            'rank': i + 1,
            'applicant': a,
            'score': raw_score(a),
            'rules': _applicant_rules(a),
        }
        for i, a in enumerate(ranked_applicants)
    ]

    # ── TAB 2: Enrolled students evaluated by rule-based engine ──────────────
    # Sync first so the table is always current
    if scholarship_type == 'Affirmative':
        AffirmativeRecommendation.evaluate_and_sync(passing_threshold)

    recommendations = (
        AffirmativeRecommendation.objects
        .select_related('student__user')
        .order_by('-fit_score', 'student__user__last_name')
    )

    # Build per-row rule breakdown from live profile data
    rec_rows = []
    for i, rec in enumerate(recommendations):
        p = rec.student
        gpa_pass   = p.shs_gpa is not None and p.shs_gpa >= passing_threshold
        exam_pass  = p.suc_exam_score is not None and p.suc_exam_score >= 50.0
        not_tes    = not p.is_tes_beneficiary
        eligible   = gpa_pass and exam_pass and not_tes
        rec_rows.append({
            'rank': i + 1 if eligible else None,
            'rec': rec,
            'profile': p,
            'gpa_pass': gpa_pass,
            'exam_pass': exam_pass,
            'not_tes': not_tes,
            'eligible': eligible,
        })

    # Sort: eligible first (by fit_score desc), then ineligible
    rec_rows.sort(key=lambda r: (0 if r['eligible'] else 1, -r['rec'].fit_score))
    # Re-assign ranks only to eligible rows
    rank_counter = 1
    for row in rec_rows:
        if row['eligible']:
            row['rank'] = rank_counter
            rank_counter += 1
        else:
            row['rank'] = None

    eligible_count   = sum(1 for r in rec_rows if r['eligible'])
    ineligible_count = sum(1 for r in rec_rows if not r['eligible'])

    return render(request, 'vpsea/ranking.html', {
        'applicant_rows': applicant_rows,
        'rec_rows': rec_rows,
        'scholarship_types': scholarship_types,
        'active_type': scholarship_type,
        'tab': tab,
        'passing_threshold': passing_threshold,
        'eligible_count': eligible_count,
        'ineligible_count': ineligible_count,
        'total_applicants': len(ranked_applicants),
    })


@login_required(login_url='/login/')
def student_apply_tes(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    existing = TESApplication.objects.filter(student=profile).first() if profile else None
    if request.method == 'POST' and profile and not existing:
        p = request.POST
        # The student's own middle name and both parents' names come from the
        # profile now, so the form shows them read-only and the application
        # does not keep a second copy that could drift out of step.
        TESApplication.objects.create(
            student=profile,
            lrn=p.get('lrn', ''),
            birthdate=p.get('birthdate') or None,
            complete_program=p.get('complete_program', ''),
            street_barangay=p.get('street_barangay', ''),
            city_municipality=p.get('city_municipality', ''),
            province=p.get('province', ''),
            region=p.get('region', ''),
            zip_code=p.get('zip_code', ''),
            contact_number=p.get('contact_number', ''),
            email_address=p.get('email_address', ''),
            disability_type=p.get('disability_type', 'N/A'),
            is_solo_parent_dependent=p.get('is_solo_parent_dependent') == '1',
            is_first_gen_college=p.get('is_first_gen_college') == '1',
            indigenous_people_group=p.get('indigenous_people_group', 'Not Applicable'),
        )
        return redirect('/student/apply/tes/?submitted=1')
    return render(request, 'student/apply_tes.html', {
        'profile': profile,
        'existing': existing,
        'submitted': request.GET.get('submitted'),
        'enrolled': _is_enrolled(profile),
        'post': request.POST if request.method == 'POST' else (
            {
                'lrn': existing.lrn,
                'birthdate': existing.birthdate.strftime('%Y-%m-%d') if existing.birthdate else '',
                'complete_program': existing.complete_program,
                'street_barangay': existing.street_barangay,
                'city_municipality': existing.city_municipality,
                'province': existing.province,
                'region': existing.region,
                'zip_code': existing.zip_code,
                'contact_number': existing.contact_number,
                'email_address': existing.email_address,
                'disability_type': existing.disability_type,
                'is_solo_parent_dependent': '1' if existing.is_solo_parent_dependent else '0',
                'is_first_gen_college': '1' if existing.is_first_gen_college else '0',
                'indigenous_people_group': existing.indigenous_people_group,
            } if existing else {}
        ),
    })


@_unifast_required
def unifast_tes_ranking(request):
    """Rule-based TES ranking and recommendation, for the office that awards it.

    Reads the student records UniFAST already holds and concludes nothing it
    cannot evidence. api/tes_ranking.py carries the rules, the field each one
    reads, and the reason it reports back.
    """
    from . import tes_ranking

    # Students still waiting on a decision — the ones this list exists to
    # choose between. Ranking every profile on file put people who never asked
    # for TES onto an award list; ranking approved and rejected applicants put
    # people there whose case is already closed.
    applicants = (
        StudentProfile.objects
        .filter(tes_applications__status='Pending')
        .select_related('user')
        .prefetch_related('tes_applications')
        .distinct()
    )
    evaluations = tes_ranking.rank(applicants)

    # The ranked list holds only applicants whose record is complete. A rank is
    # a position against other students, and an incomplete record cannot support
    # one — so those applicants are held in their own list instead of being
    # given a number, and instead of being dropped, which would lose exactly the
    # people who need chasing. Not Eligible stays out of both lists and is
    # reported in the summary cards.
    ranked = [e for e in evaluations if e.status == tes_ranking.ELIGIBLE]
    for position, evaluation in enumerate(ranked, start=1):
        evaluation.rank = position
    needs_info = [e for e in evaluations if e.status == tes_ranking.FOR_VERIFICATION]

    return render(request, 'unifast/tes_ranking.html', {
        'active': 'tes_ranking',
        'tes_rows': ranked,
        'tes_needs_info': needs_info,
        'tes_applicant_total': len(evaluations),
        'tes_counts': {
            'eligible': sum(1 for e in evaluations if e.status == tes_ranking.ELIGIBLE),
            'verification': sum(1 for e in evaluations if e.status == tes_ranking.FOR_VERIFICATION),
            'not_eligible': sum(1 for e in evaluations if e.status == tes_ranking.NOT_ELIGIBLE),
            'priority_1': sum(1 for e in evaluations if e.priority == tes_ranking.PRIORITY_1),
            'priority_2': sum(1 for e in evaluations if e.priority == tes_ranking.PRIORITY_2),
        },
    })


@_unifast_required
def unifast_tes_applications(request):
    if request.method == 'POST':
        app_id = request.POST.get('app_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        TESApplication.objects.filter(id=app_id).update(status=new_status, remarks=remarks)
        return redirect('/unifast/tes-applications/?saved=1')
    apps = TESApplication.objects.select_related('student__user').order_by('-submitted_at')
    return render(request, 'unifast/tes_applications.html', {
        'applications': apps,
        'total': apps.count(),
        'pending_count': apps.filter(status='Pending').count(),
        'approved_count': apps.filter(status='Approved').count(),
    })


@_unifast_required
def unifast_tes_review(request, pk):
    if request.method == 'POST':
        new_status = request.POST.get('status', 'Pending')
        remarks = request.POST.get('remarks', '')
        award_number = request.POST.get('award_number', '')
        TESApplication.objects.filter(pk=pk).update(
            status=new_status,
            remarks=remarks,
            award_number=award_number,
        )
        if new_status == 'Approved':
            from .models import SystemSettings
            try:
                tes_app = TESApplication.objects.select_related('student').get(pk=pk)
                scholarship = Scholarship.objects.filter(type='TES').first()
                if scholarship:
                    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
                    parsed = SystemSettings.parse_label(settings_obj.academic_year)
                    already = Application.objects.filter(
                        student=tes_app.student, scholarship=scholarship,
                        school_year=parsed['sy'], semester=parsed['semester'],
                    ).exists()
                    if not already:
                        Application.objects.create(
                            student=tes_app.student,
                            scholarship=scholarship,
                            status='Approved',
                            remarks=remarks,
                            source='tes_application',
                            tes_application_id=pk,
                            school_year=parsed['sy'],
                            semester=parsed['semester'],
                            award_number=award_number,
                        )
                    else:
                        # Update award_number on existing Application row if already present
                        Application.objects.filter(
                            student=tes_app.student, scholarship=scholarship,
                            school_year=parsed['sy'], semester=parsed['semester'],
                        ).update(
                            source='tes_application',
                            tes_application_id=pk,
                            award_number=award_number,
                        )
            except TESApplication.DoesNotExist:
                pass
    return redirect('/unifast/tes-applications/?saved=1')


@_unifast_required
def unifast_archives(request):
    from .models import ScholarListImport, SystemSettings, ImportedScholar
    db_types = list(Scholarship.objects.values_list('type', flat=True).distinct())
    archive_types = UNIFAST_TYPES + [t for t in db_types if t not in UNIFAST_TYPES and t not in ['Academic','DOST','CHED','CoScho','Sports','Affirmative','Staff','GSIS']]
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    parsed = SystemSettings.parse_label(active_label)
    active_sy = parsed['sy']
    active_semester = parsed['semester']
    stype = request.GET.get('type', 'TDP')
    if stype not in archive_types:
        stype = archive_types[0]
    history = ScholarListImport.objects.filter(scholarship_type=stype).order_by('-created_at')
    all_labels = list(ScholarListImport.objects.filter(scholarship_type=stype).values_list('term_label', flat=True).distinct().order_by('-term_label'))
    ar_labels = list(ImportedScholar.objects.exclude(term_label='').filter(scholarship_type=stype).values_list('term_label', flat=True).distinct())
    for lbl in ar_labels:
        if lbl not in all_labels:
            all_labels.append(lbl)
    all_labels = sorted(set(all_labels), reverse=True)
    if active_label not in all_labels:
        all_labels.insert(0, active_label)
    all_sy_display = [(lbl, SystemSettings.parse_label(lbl)['sy'] + ' - ' + SystemSettings.parse_label(lbl)['semester']) for lbl in all_labels]
    selected_label = request.GET.get('sy', active_label)
    if selected_label not in all_labels:
        selected_label = active_label
    yy, s = active_label.split('-')
    prev_label = f'{yy}-1' if s == '2' else f'{int(yy)-1}-2'
    prev_parsed = SystemSettings.parse_label(prev_label)
    next_label = settings_obj.next_label()
    imported_rows = ImportedScholar.objects.filter(
        scholarship_type=stype, term_label=selected_label, claimed_by__isnull=True,
    ).order_by('last_name', 'first_name')

    def sy_filter(qs):
        # See the matching helper in vpsea_archives — the term is a column now.
        return qs.filter(term_label=selected_label)

    scholars = sy_filter(
        Application.objects.filter(status='Approved', scholarship__type=stype)
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name').distinct()
    return render(request, 'unifast/archives.html', {
        'archive_types': archive_types,
        'active_type': stype,
        'scholars': scholars,
        'imported_rows': imported_rows,
        'total': scholars.count() + imported_rows.count(),
        'history': history,
        'all_sy_display': all_sy_display,
        'selected_sy': selected_label,
        'active_sy': active_label,
        'active_sy_display': active_sy + ' - ' + active_semester,
        'active_semester': active_semester,
        'next_sy': next_label,
        'prev_sy': prev_label,
        'prev_sy_display': prev_parsed['sy'] + ' - ' + prev_parsed['semester'],
    })


@_unifast_required
def unifast_archive_add(request):
    from .models import Application, Scholarship, StudentProfile, User, SystemSettings, ApplicationDocument
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    p = request.POST
    f = request.FILES
    stype = p.get('scholarship_type', 'TDP')
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    active_semester = parsed['semester']
    email = p.get('email', '').strip()
    student_id = p.get('student_id', '').strip()
    if not email:
        email = f"{student_id}@bipsu.edu.ph"
    user = User.objects.filter(email=email).first()
    if not user:
        user = User.objects.create_user(
            username=email, email=email,
            password=student_id or 'bipsu1234',
            first_name=p.get('first_name', ''),
            last_name=p.get('last_name', ''),
            role='student',
        )
    profile = StudentProfile.objects.filter(user=user).first()
    if not profile:
        from .constants import school_for_course
        profile = StudentProfile.objects.create(
            user=user,
            student_id=student_id,
            middle_name=p.get('middle_name', '').strip(),
            school=school_for_course(p.get('course', '')),
            course=p.get('course', ''),
            year_level=int(p.get('year_level', 1) or 1),
            gwa=float(p.get('gwa', 0) or 0),
            gender=p.get('gender', ''),
            barangay=p.get('barangay', ''),
            municipality=p.get('municipality', ''),
            province=p.get('province', ''),
            contact_number=p.get('contact_number', ''),
            date_of_birth=p.get('date_of_birth') or None,
        )
    else:
        profile.course = p.get('course', profile.course)
        profile.year_level = int(p.get('year_level', profile.year_level) or profile.year_level)
        profile.gender = p.get('gender', profile.gender)
        profile.barangay = p.get('barangay', profile.barangay)
        profile.municipality = p.get('municipality', profile.municipality)
        profile.province = p.get('province', profile.province)
        profile.save()
    scholarship = Scholarship.objects.filter(type=stype).first()
    if scholarship:
        award_fields = {
            'source': 'import',
            'school_year': active_sy,
            'semester': active_semester,
            'award_number': p.get('award_number', ''),
            'congress_district': p.get('congress_district', ''),
        }
        already = Application.objects.filter(
            student=profile, scholarship=scholarship,
            school_year=active_sy, semester=active_semester,
        ).exists()
        if not already:
            app = Application.objects.create(
                student=profile, scholarship=scholarship,
                status='Approved', **award_fields,
            )
        else:
            app = Application.objects.filter(
                student=profile, scholarship=scholarship,
                school_year=active_sy, semester=active_semester,
            ).first()
        for field, label in [
            ('doc_certificate_of_grades', 'Certificate Of Grades'),
            ('doc_certificate_of_enrollment', 'Certificate Of Enrollment'),
            ('doc_prospectus', 'Prospectus'),
            ('doc_id_photo', 'Id Photo'),
            ('doc_application_form', 'Application Form'),
            ('proof_document', 'Proof Document'),
        ]:
            uploaded = f.get(field)
            if uploaded:
                ApplicationDocument.objects.create(application=app, name=label, file=uploaded)
    return redirect(f'/unifast/archives/?type={stype}&added=1')


@_unifast_required
def unifast_archive_edit(request, pk):
    from .models import Application
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    p = request.POST
    stype = p.get('scholarship_type', 'TDP')
    try:
        app = Application.objects.select_related('student__user').get(pk=pk)
    except Application.DoesNotExist:
        return redirect(f'/unifast/archives/?type={stype}')
    profile = app.student
    user = profile.user
    user.first_name = p.get('first_name', user.first_name)
    user.last_name = p.get('last_name', user.last_name)
    user.save()
    profile.course = p.get('course', profile.course)
    profile.year_level = int(p.get('year_level', profile.year_level) or profile.year_level)
    profile.gender = p.get('gender', profile.gender)
    profile.barangay = p.get('barangay', profile.barangay)
    profile.municipality = p.get('municipality', profile.municipality)
    profile.province = p.get('province', profile.province)
    if p.get('student_id'):
        profile.student_id = p.get('student_id')
    profile.save()
    if p.get('award_number') is not None:
        app.award_number = p.get('award_number')
    if p.get('congress_district') is not None:
        app.congress_district = p.get('congress_district')
    app.save()
    return redirect(f'/unifast/archives/?type={stype}&edited=1')


@_unifast_required
def unifast_archive_delete(request, pk):
    from .models import Application
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    stype = request.POST.get('scholarship_type', 'TDP')
    Application.objects.filter(pk=pk).delete()
    return redirect(f'/unifast/archives/?type={stype}&deleted=1')


@_unifast_required
def unifast_archive_import(request):
    from django.core.files.base import ContentFile
    from .models import ScholarListImport, ActivityLog, SystemSettings, ImportedScholar
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    stype = request.POST.get('type', 'TDP')
    rollover_label = request.POST.get('rollover_label', '').strip()
    file = request.FILES.get('file')
    if not file:
        return redirect(f'/unifast/archives/?type={stype}&import_error=No+file+provided')
    if not rollover_label:
        return redirect(f'/unifast/archives/?type={stype}&import_error=Rollover+name+is+required')
    try:
        import openpyxl
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        parsed = SystemSettings.parse_label(settings_obj.academic_year)
        active_semester = parsed['semester']
        rollover_parsed = SystemSettings.parse_label(rollover_label) if '-' in rollover_label else {'sy': rollover_label, 'semester': active_semester}
        wb = openpyxl.load_workbook(file)
        ws = wb.active
        col_map = COLUMN_MAPS.get(stype, COLUMN_MAPS['CoScho'])
        ImportedScholar.objects.filter(scholarship_type=stype, term_label=rollover_label).delete()
        records = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue
            try:
                int(row[0])
            except (ValueError, TypeError):
                continue
            extra = {}
            for idx, field in col_map:
                val = row[idx] if idx < len(row) else None
                extra[field] = str(val).strip() if val is not None else ''
            last = extra.get('last_name', '').strip()
            first = extra.get('first_name', '').strip()
            if not last and not first:
                continue
            try:
                year_level = int(extra.get('year', 0) or 0)
            except (ValueError, TypeError):
                year_level = 0
            try:
                gwa = float(extra.get('gwa', 0) or 0)
            except (ValueError, TypeError):
                gwa = 0.0
            records.append(ImportedScholar(
                scholarship_type=stype,
                term_label=rollover_label,
                last_name=last,
                first_name=first,
                middle_name=extra.get('middle_name', extra.get('middle_initial', '')),
                gender=extra.get('sex', ''),
                course=extra.get('course', ''),
                year=year_level,
                gwa=gwa,
                barangay=extra.get('barangay', ''),
                municipality=extra.get('municipality', ''),
                province=extra.get('province', ''),
                student_id=extra.get('student_number', extra.get('student_id', '')),
                award_number=extra.get('award_number', ''),
                congress_district=extra.get('congress_district', ''),
                imported_from=file.name,
            ))
        ImportedScholar.objects.bulk_create(records)
        created = len(records)
        file.seek(0)
        if not ScholarListImport.objects.filter(term_label=rollover_label, scholarship_type=stype).exists():
            rollover = ScholarListImport(
                scholarship_type=stype,
                school_year=rollover_parsed['sy'],
                semester=rollover_parsed.get('semester', active_semester),
                term_label=rollover_label,
                scholar_count=created,
                imported_by=request.user,
            )
            rollover.excel_file.save(f'{stype}_{rollover_label}.xlsx', ContentFile(file.read()), save=True)
        else:
            ScholarListImport.objects.filter(term_label=rollover_label, scholarship_type=stype).update(scholar_count=created)
        ActivityLog.objects.create(
            user=request.user,
            action=f'Imported {file.name} ({created} rows) for {stype} as "{rollover_label}"'
        )
    except Exception as e:
        return redirect(f'/unifast/archives/?type={stype}&import_error={e}')
    return redirect(f'/unifast/archives/?type={stype}&import_ok={created}')


@_unifast_required
def unifast_rollover_delete(request, pk):
    from .models import ScholarListImport
    if request.method != 'POST':
        return redirect('/unifast/archives/')
    stype = request.POST.get('type', 'TDP')
    try:
        r = ScholarListImport.objects.get(pk=pk)
        r.excel_file.delete(save=False)
        r.delete()
    except ScholarListImport.DoesNotExist:
        pass
    return redirect(f'/unifast/archives/?type={stype}')


@_unifast_required
def unifast_archive_download(request):
    from django.http import HttpResponse
    from io import BytesIO
    from .models import SystemSettings
    from django.db.models import Q
    stype = request.GET.get('type', 'TDP')
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    semester = settings_obj.active_semester
    scholars = Application.objects.filter(
        status='Approved', scholarship__type=stype
    ).select_related('student__user', 'scholarship').order_by('student__user__last_name')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'{stype} Scholars'
    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hfont = Font(bold=True)
    hfill = PatternFill('solid', fgColor='D9E1F2')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    headers = ['No.', 'Last Name', 'First Name', 'Gender', 'Course', 'Year Level', 'Student ID', 'Award No.', 'Congress District', 'Barangay', 'Municipality', 'Province']
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = hfont; cell.fill = hfill; cell.border = border; cell.alignment = center
    for i, app in enumerate(scholars, 1):
        p = app.student
        ws.append([i, p.user.last_name, p.user.first_name, p.gender, p.course, p.year_level,
                   p.student_id, app.award_number,
                   app.congress_district,
                   p.barangay, p.municipality, p.province])
    for col in ws.columns:
        ml = max((len(str(c.value)) for c in col if c.value), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(ml + 4, 40)
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    filename = f'{stype}_scholars_{settings_obj.academic_year}_{semester.replace(" ", "_")}.xlsx'
    response = HttpResponse(buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── BiPSU Staff portal ─────────────────────────────────────────────────────────

def _nsu_staff_required(view_fn):
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'nsu_staff':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper


def _staff_profile(user):
    """The staff member's own record, created on first visit if it is missing.

    Migration 0032 backfilled a profile for every staff account that existed
    when it ran, but accounts created since — and any created outside the
    registration form — have none, so the portal cannot assume a row is there.
    """
    from .models import StaffProfile
    profile, _ = StaffProfile.objects.get_or_create(user=user)
    return profile


def _parse_date(raw):
    """('2016-06-01' | '' | 'nonsense') -> (date | None, ok?).

    Blank clears the field, which is a valid edit; anything unparseable is
    reported back instead of being handed to the DB, which errors out on save.
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
    """The application's value if it has one, else the staff profile's."""
    value = getattr(application, field, '') if application else ''
    return value or getattr(staff, field, '') or ''


def _pick_date(application, staff, field):
    """:func:`_pick` for a date field, rendered for a date input."""
    value = getattr(application, field, None) if application else None
    value = value or getattr(staff, field, None)
    return value.strftime('%Y-%m-%d') if value else ''


def _nsu_staff_enrolled(user):
    """True when the staff member has any non-rejected application — the Apply link is hidden."""
    from .models import AffirmativeStaffApplication
    return AffirmativeStaffApplication.objects.filter(
        email=user.email,
    ).exclude(status='Rejected').exists()


@_nsu_staff_required
def nsu_staff_dashboard(request):
    from .models import StaffRenewal, Notification, Announcement, AffirmativeStaffApplication
    user = request.user
    # Try to find the matching AffirmativeStaffApplication record for this staff member
    aff_app = AffirmativeStaffApplication.objects.filter(
        email=user.email, qualified_for='Staff'
    ).exclude(status='Rejected').first()
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
    """The staff member's own record. Employment details are edited here.

    They used to be written straight into the AffirmativeStaffApplication the
    office had reviewed. They live on StaffProfile now, so correcting a
    department or an employee ID no longer edits an approved award — the
    application is shown below, read-only, as the snapshot it is.
    """
    from .models import AffirmativeStaffApplication, StaffProfile
    from .constants import CIVIL_STATUSES, DESIGNATIONS, EMPLOYMENT_STATUSES
    user = request.user
    staff = _staff_profile(user)
    # Any status, not only Approved — a staff member whose application is still
    # Pending Validation or Needs Revision has to be able to see where it stands.
    # Latest wins if they re-applied after a rejection.
    aff_app = AffirmativeStaffApplication.objects.filter(
        email=user.email, qualified_for='Staff'
    ).order_by('-submitted_at').first()
    saved = False
    errors = []
    if request.method == 'POST':
        p = request.POST
        # Only the given and family names live on the User row; every other
        # detail belongs to the profile.
        user.first_name = p.get('first_name', user.first_name).strip()
        user.last_name  = p.get('last_name',  user.last_name).strip()
        user.save()

        # Personal
        staff.middle_name    = p.get('middle_name', staff.middle_name).strip()
        staff.suffix         = p.get('suffix', staff.suffix).strip()
        staff.gender         = p.get('gender', staff.gender)
        staff.civil_status   = p.get('civil_status', staff.civil_status)
        staff.contact_number = p.get('contact_number', staff.contact_number).strip()
        staff.barangay       = p.get('barangay', staff.barangay)
        staff.municipality   = p.get('municipality', staff.municipality)
        staff.province       = p.get('province', staff.province)

        # Employment
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

        # Only read when the hiring date is unknown — see the model property.
        yos = p.get('years_of_service', '').strip()
        if yos == '':
            staff.declared_years_of_service = None
        elif yos.isdigit():
            staff.declared_years_of_service = int(yos)
        else:
            errors.append('Years of service must be a whole number of years.')

        if request.FILES.get('appointment_paper'):
            staff.appointment_paper = request.FILES['appointment_paper']

        # The valid fields in a submission go through even when another one was
        # rejected, so a single typo does not throw the whole form away.
        staff.save()
        saved = not errors
    return render(request, 'nsu_staff/profile.html', {
        'staff': staff,
        'aff_app': aff_app,
        'saved': saved,
        'errors': errors,
        'bipsu_schools': BIPSU_SCHOOLS,
        'civil_statuses': CIVIL_STATUSES,
        'employment_statuses': EMPLOYMENT_STATUSES,
        'designations': DESIGNATIONS,
        'enrolled': _nsu_staff_enrolled(user),
    })


@_nsu_staff_required
def nsu_staff_notifications(request):
    from .models import Notification
    user = request.user
    # Notifications are tied to StudentProfile; staff may not have one — guard gracefully
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
    from .models import AffirmativeStaffApplication, StaffRenewal
    user = request.user
    applications = AffirmativeStaffApplication.objects.filter(
        email=user.email
    ).order_by('-submitted_at')
    renewals = StaffRenewal.objects.filter(staff_user=user).order_by('-submitted_at')
    return render(request, 'nsu_staff/applications.html', {
        'applications': applications,
        'renewals': renewals,
        'enrolled': _nsu_staff_enrolled(user),
    })


@_nsu_staff_required
def nsu_staff_renewal(request):
    from .models import StaffRenewal, SystemSettings
    user = request.user
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    renewals = StaffRenewal.objects.filter(staff_user=user).order_by('-submitted_at')
    errors = []
    submitted = False

    if request.method == 'POST':
        sup = request.FILES.get('supporting_document')
        if not errors:
            StaffRenewal.objects.create(
                staff_user=user,
                supporting_document=sup or None,
            )
            return redirect('/nsu-staff/renewal/?submitted=1')
        return render(request, 'nsu_staff/renewal.html', {
            'renewals': renewals, 'errors': errors,
            'semester': parsed['semester'], 'academic_year': parsed['sy'],
            'enrolled': _nsu_staff_enrolled(user),
        })

    return render(request, 'nsu_staff/renewal.html', {
        'renewals': renewals,
        'submitted': request.GET.get('submitted'),
        'semester': parsed['semester'],
        'academic_year': parsed['sy'],
        'errors': errors,
        'enrolled': _nsu_staff_enrolled(user),
    })


@_nsu_staff_required
def nsu_staff_apply(request):
    from .models import AffirmativeStaffApplication, SystemSettings
    user = request.user
    staff = _staff_profile(user)

    # Check if already has an approved/pending application — Draft is still editable
    existing = AffirmativeStaffApplication.objects.filter(
        email=user.email, qualified_for='Staff'
    ).exclude(status='Rejected').first()

    if existing and existing.status in ('Approved', 'Pending Validation'):
        return render(request, 'nsu_staff/apply.html', {
            'blocked': True,
            'blocked_reason': f'You already have a Staff Scholarship application with status: {existing.status}.',
            'existing': existing,
            'enrolled': True,
        })

    errors = []

    if request.method == 'POST':
        p = request.POST
        f = request.FILES
        action = p.get('action', 'submit')  # 'draft' or 'submit'
        is_draft = action == 'draft'

        # Required field validation — skip for draft
        if not is_draft:
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

            # A regular appointment is the whole eligibility rule for this
            # programme — there is nothing else to qualify on.
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

            new_status = 'Draft' if is_draft else 'Pending Validation'

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
                existing.status = new_status
                if not is_draft:
                    existing.remarks = ''
                if f.get('appointment_paper'):
                    existing.appointment_paper = f.get('appointment_paper')
                existing.save()
            else:
                existing = AffirmativeStaffApplication.objects.create(
                    full_name=full_name,
                    email=user.email,
                    contact_number=p.get('contact_number', ''),
                    barangay=p.get('barangay', ''),
                    municipality=p.get('municipality', ''),
                    province=p.get('province', ''),
                    date_of_birth=p.get('date_of_birth') or '2000-01-01',
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
                    status=new_status,
                )
            # The application is the snapshot the office reviews; the profile
            # is the live record. What the staff member just entered about
            # themselves belongs on both.
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
            # Point at the file the application just stored rather than
            # uploading a second copy of the same document.
            if existing.appointment_paper:
                staff.appointment_paper = existing.appointment_paper.name
            staff.save()

            param = 'drafted' if is_draft else 'submitted'
            return redirect(f'/nsu-staff/apply/?{param}=1')

    return render(request, 'nsu_staff/apply.html', {
        'blocked': False,
        'existing': existing,
        'submitted': request.GET.get('submitted'),
        'drafted': request.GET.get('drafted'),
        'errors': errors,
        'user': user,
        'bipsu_courses': BIPSU_COURSES,
        'bipsu_schools': BIPSU_SCHOOLS,
        'enrolled': _nsu_staff_enrolled(user),
        # Pre-fill from existing draft/rejected record, or fall back to the
        # User's account fields so the staff member doesn't retype their own info.
        # Filled from the draft/rejected application first, then from the staff
        # member's own profile, then from their account — so nothing already on
        # file has to be retyped.
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
