from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.clickjacking import xframe_options_exempt
from . import scholar_columns
from .models import STAFF_APPLICATION_DETAILS, STUDENT_DETAILS, StudentProfile, Scholarship, Application, Notification, Announcement, User, AffirmativeStaffApplication, AcademicRenewal, ScholarshipLinkRequest, BIPSU_SCHOOLS, BIPSU_COURSES, split_ched
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from django.db import transaction
from . import notify
from django.http import HttpResponse
from datetime import date
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


def landing_view(request):
    qs = Scholarship.objects.filter(is_active=True).order_by('type')
    return render(request, 'landing.html', {
        'scholarships': qs,
        'internal': qs.filter(group='internal'),
        'external': qs.filter(group='external'),
        'institutional': qs.filter(group='institutional'),
    })


PORTAL_FOR_ROLE = {
    'student': '/student/applications/',
    'nsu_staff': '/nsu-staff/',
    'vpsea': '/vpsea/',
    'partner': '/partner/',
    'super': '/super/',
}


def _portal_for(user):
    return PORTAL_FOR_ROLE.get(user.role, '/')


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_portal_for(request.user))

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password') or ''
        user = authenticate(request, username=email, password=password)
        if user and not user.can_sign_in:
            return render(request, 'login.html', {
                'verification_status': user.verification_status,
                'verification_note': user.verification_note,
            })
        if user:
            login(request, user)
            return redirect(_portal_for(user))
        return render(request, 'login.html', _sign_in_error(email, password))
    return render(request, 'login.html')


def _sign_in_error(email, password):
    ctx = {'email': email}

    if not email:
        ctx['error'] = 'Enter the email address you registered with.'
        return ctx
    if not password:
        ctx['error'] = 'Enter your password.'
        return ctx

    account = User.objects.filter(email__iexact=email).first()
    if account is None:
        ctx['error'] = (
            f'No account is registered under {email}. Check the address for a '
            'typo, or register first if you have not yet.'
        )
        ctx['error_action'] = 'register'
        return ctx

    if not account.is_active:
        ctx['error'] = (
            'That account has been deactivated. Contact the SDSO office to have '
            'it reopened.'
        )
        return ctx

    ctx['error'] = (
        f'The password does not match the account for {email}. Check your '
        'capitals — passwords are case-sensitive.'
    )
    return ctx


def logout_view(request):
    logout(request)
    return redirect('/')


def _await_verification(request, user):
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
        'waiting': bool(account) and account.awaiting_verification,
        'confirm_email': bool(account) and not account.email_verified,
        'confirmed': request.GET.get('confirmed') == '1',
        'resent': request.GET.get('resent') == '1',
        'confirm_error': request.GET.get('confirm_error', ''),
    })


def verify_email(request, token):
    from . import email_verify
    from .middleware import PENDING_EMAIL
    from urllib.parse import quote

    account, reason = email_verify.read_token(token)
    if account is None:
        message = {
            'expired': 'That confirmation link has expired. Registrations are '
                       'confirmed within three days — ask for a new link below.',
            'stale': 'That link was sent to a different address than the one on '
                     'the account now. Ask for a new link below.',
        }.get(reason, 'That confirmation link is not valid. Check that you '
                      'copied the whole of it, or ask for a new one below.')
        return redirect(f'/register/received/?confirm_error={quote(message)}')

    account.mark_email_verified()
    if not request.session.get(PENDING_EMAIL):
        request.session[PENDING_EMAIL] = account.email
    return redirect('/register/received/?confirmed=1')


def resend_confirmation(request):
    from . import email_verify
    from .middleware import PENDING_EMAIL
    from urllib.parse import quote

    if request.method != 'POST':
        return redirect('/register/received/')

    email = request.session.get(PENDING_EMAIL, '')
    account = User.objects.filter(email=email).first() if email else None
    if account is None:
        return redirect('/register/received/?confirm_error=' + quote(
            'There is no registration on this browser to send a link for. '
            'Sign in with the email and password you registered with.'))
    if account.email_verified:
        return redirect('/register/received/?confirmed=1')

    email_verify.send_confirmation(account, request)
    return redirect('/register/received/?resent=1')


def _release_rejected_registration(email, student_id):
    from django.db.models import Q

    from .models import ActivityLog

    claimed = Q(email=email)
    if student_id:
        claimed |= Q(profile__student_id=student_id)

    rejected = User.objects.filter(claimed, verification_status='rejected').distinct()

    for account in rejected:
        held = account.email
        profile = getattr(account, 'profile', None)
        if profile and profile.student_id:
            held += f' / {profile.student_id}'
        reason = account.verification_note or 'no reason recorded'
        ActivityLog.objects.create(
            user=None,
            action=(f'Rejected registration replaced by a new one — {held} '
                    f'— original reason: {reason}'),
        )
        account.delete()


def _declaration_slots(post=None):
    post = post or {}
    slots = []
    for number, suffix in enumerate(DECLARATION_SLOTS, start=1):
        tail = '' if not suffix else str(number)
        slots.append({
            'n': number,
            'suffix': suffix,
            'extra': bool(suffix),
            'card_id': f'scholarshipData{tail}',
            'tier_id': f'chedTier{tail}',
            'type_id': f'scholarshipType{tail}',
            'open': bool(post.get(f'has_scholarship{suffix}')),
            'type': post.get(f'scholarship_type{suffix}', ''),
            'tier': post.get(f'award_tier{suffix}', ''),
            'award_number': post.get(f'award_number{suffix}', ''),
            'notes': post.get(f'notes{suffix}', ''),
        })
    return slots


def _register_context(post=None):
    import json
    from . import terms
    from .constants import (CIVIL_STATUSES, DECLARABLE_SCHOLARSHIP_TYPES,
                            GENDERS, STAFF_DECLARABLE_LABEL)
    from .models import CHED_TIER_CHOICES, SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return {
        'bipsu_schools': BIPSU_SCHOOLS,
        'bipsu_courses_json': json.dumps(BIPSU_COURSES),
        'civil_statuses': CIVIL_STATUSES,
        'genders': GENDERS,
        'scholarship_types': DECLARABLE_SCHOLARSHIP_TYPES,
        'staff_scholarship_label': STAFF_DECLARABLE_LABEL,
        'ched_tiers': CHED_TIER_CHOICES,
        'max_upload_mb': settings_obj.max_file_size_mb or 5,
        'declaration_slots': _declaration_slots(post),
        **terms.context(),
        **_disability_fields(
            (post or {}).get('disability_type') if post is not None else None,
            (post or {}).get('disability_type_other', ''),
            ''),
    }


def _registration_profile_fields(p, files, disability):
    from .constants import school_for_course
    course = p.get('course', '')
    fields = {
        'school': p.get('school', '').strip() or school_for_course(course),
        'course': course,
        'year_level': int(p.get('year_level', 1) or 1),
        'middle_name': p.get('middle_name', '').strip(),
        'suffix': p.get('suffix', '').strip(),
        'birth_place': p.get('birth_place', '').strip(),
        'civil_status': p.get('civil_status', '').strip(),
        'date_of_birth': p.get('date_of_birth') or None,
        'gender': p.get('gender', ''),
        'contact_number': p.get('contact_number', ''),
        'disability_type': disability,
        'barangay': p.get('barangay', '').strip(),
        'municipality': p.get('municipality', '').strip(),
        'province': p.get('province', '').strip(),
        'elementary': p.get('elementary', '').strip(),
        'highschool': p.get('highschool', '').strip(),
        'highschool_is_public': _tristate(p.get('highschool_is_public'), None),
        'last_school': p.get('last_school', '').strip(),
        'family_income': _decimal_or(p.get('family_income'), 0.0),
        'indigenous_group': p.get('indigenous_group', '').strip(),
        'is_from_depressed_area': _tristate(p.get('is_from_depressed_area'), None),
        'shs_gpa': _decimal_or(p.get('shs_gpa'), None),
        'suc_exam_score': _decimal_or(p.get('suc_exam_score'), None),
        'suc_exam_total': _decimal_or(p.get('suc_exam_total'), None) or None,
        'is_tes_beneficiary': 'is_tes_beneficiary' in p,
        'citizenship': p.get('citizenship', '').strip(),
        'household_size': _positive_int(p.get('household_size'), None),
        'year_first_enrolled': _positive_int(p.get('year_first_enrolled'), None),
        'is_listahanan_household': _tristate(p.get('is_listahanan_household'), None),
        'is_4ps_beneficiary': _tristate(p.get('is_4ps_beneficiary'), None),
        'has_previous_degree': _tristate(p.get('has_previous_degree'), None),
        'is_solo_parent_dependent': _tristate(p.get('is_solo_parent_dependent'), None),
    }
    for name in ('shs_gpa_cert', 'suc_exam_cert'):
        if files.get(name):
            fields[name] = files[name]
    return fields


def _decimal_or(raw, fallback):
    try:
        return float((raw or '').strip())
    except (TypeError, ValueError):
        return fallback


def _certificate_errors(files):
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    errors = []
    for field, label in (('shs_gpa_cert', 'SHS GPA Certificate'),
                         ('suc_exam_cert', 'SUC Exam Certificate')):
        upload = files.get(field)
        if upload:
            errors += [f'{label}: {problem}'
                       for problem in _validate_proof(upload, settings_obj)]
    return errors


DECLARATION_SLOTS = ('', '_2', '_3')


def _declared_scholarship(p, files, slot=''):
    from .constants import DECLARABLE_SCHOLARSHIP_TYPES
    from .models import CHED_TIER_CHOICES, SystemSettings
    if f'has_scholarship{slot}' not in p:
        return None, []

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    stype = p.get(f'scholarship_type{slot}', '')
    tier = p.get(f'award_tier{slot}', '') if stype == 'CHED' else ''
    proof = files.get(f'proof_document{slot}')
    where = f' (scholarship {DECLARATION_SLOTS.index(slot) + 1})' if slot else ''

    errors = []
    if stype not in [t for t, _ in DECLARABLE_SCHOLARSHIP_TYPES]:
        errors.append(f'Say which scholarship you already hold{where}, or clear the '
                      '"I already hold a scholarship" box.')
    elif stype == 'CHED' and tier not in [t for t, _ in CHED_TIER_CHOICES]:
        errors.append(f'Please choose whether your CHED award{where} is Full Merit / '
                      'Full Scholar or Half Merit / Partial Scholar — your award '
                      'letter says which.')
    errors += [f'{problem}{where}' if where else problem
               for problem in _validate_proof(proof, settings_obj)]
    if errors:
        return None, errors

    return dict(
        scholarship_type=stype,
        proof_document=proof,
        award_number=p.get(f'award_number{slot}', '').strip(),
        award_tier=tier,
        notes=p.get(f'notes{slot}', ''),
        term_label=settings_obj.academic_year,
    ), []


def _declared_scholarships(p, files):
    declarations, errors, seen = [], [], set()
    for slot in DECLARATION_SLOTS:
        declared, problems = _declared_scholarship(p, files, slot)
        errors.extend(problems)
        if not declared:
            continue
        if declared['scholarship_type'] in seen:
            from .constants import DECLARABLE_SCHOLARSHIP_TYPES
            label = dict(DECLARABLE_SCHOLARSHIP_TYPES).get(
                declared['scholarship_type'], declared['scholarship_type'])
            errors.append(f'You named the {label} twice. Declare each scholarship '
                          'once — the office verifies them one at a time.')
            continue
        seen.add(declared['scholarship_type'])
        declarations.append(declared)
    return declarations, errors


def _declared_staff_scholarship(p, files):
    from .models import SystemSettings
    if 'has_staff_scholarship' not in p:
        return None, []

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    errors = _validate_proof(files.get('staff_proof_document'), settings_obj)
    if errors:
        return None, errors

    return dict(
        proof_document=files.get('staff_proof_document'),
        notes=p.get('staff_notes', ''),
        term_label=settings_obj.academic_year,
    ), []


_REQUIRED_OF_EVERYONE = (
    ('first_name', 'First Name'),
    ('last_name', 'Last Name'),
    ('middle_name', 'Middle Name'),
    ('contact_number', 'Contact Number'),
)

_REQUIRED_OF_A_STUDENT = (
    ('date_of_birth', 'Date of Birth'),
    ('gender', 'Gender'),
    ('birth_place', 'Birth Place'),
    ('civil_status', 'Civil Status'),
    ('barangay', 'Barangay / Street'),
    ('municipality', 'Municipality'),
    ('province', 'Province'),
    ('school', 'School'),
    ('course', 'Course'),
    ('year_level', 'Year Level'),
    ('elementary', 'Elementary School'),
    ('highschool', 'High School'),
    ('last_school', 'Last School Attended'),
    ('family_income', 'Annual Family Income'),
)

_REQUIRED_AFFIRMATIVE_ANSWERS = (
    ('highschool_is_public', 'Was your high school a public school?'),
    ('is_from_depressed_area', 'Are you from a depressed area?'),
)

_REQUIRED_OF_AN_APPLICANT = (
    ('shs_gpa', 'SHS Grade Point Average'),
    ('suc_exam_score', 'SUC Admission Exam Score'),
    ('suc_exam_total', 'SUC Admission Exam Total'),
    ('citizenship', 'Citizenship'),
    ('household_size', 'Household Size'),
    ('year_first_enrolled', 'Year You First Enrolled in This Course'),
)

_REQUIRED_TES_ANSWERS = (
    ('is_listahanan_household', 'Listed in the DSWD Listahanan?'),
    ('is_4ps_beneficiary', '4Ps (Pantawid Pamilya) Beneficiary?'),
    ('is_solo_parent_dependent', 'Dependent of a solo parent?'),
    ('has_previous_degree', 'Do you already hold a college degree?'),
)

_REQUIRED_OF_STAFF = (
    ('school_id', 'School / Employee ID'),
    ('staff_school', 'Office / College / Unit'),
    ('department', 'Department'),
    ('position', 'Position'),
)


def _unanswered(posted, questions):
    return [f'{label} is required.' for name, label in questions
            if not (posted.get(name) or '').strip()]


def _unanswered_tes(posted, questions):
    return [f'{label} — please answer Yes or No.' for name, label in questions
            if (posted.get(name) or '').strip().casefold() not in ('yes', 'no')]


def register_view(request):
    if request.method == 'POST':
        p = request.POST
        errors = []
        account_type = p.get('account_type', 'student')

        from django.utils import timezone

        from . import email_verify, terms

        errors += _unanswered(p, _REQUIRED_OF_EVERYONE)

        if not p.get('accept_terms'):
            errors.append('You must read and accept the Terms of Use and Data '
                          'Privacy Notice before an account can be created.')
        posted_version = (p.get('terms_version') or '').strip()
        if posted_version and posted_version != terms.VERSION:
            errors.append('The Terms of Use and Data Privacy Notice was updated '
                          'while you were filling this form in. Please read the '
                          'current version and agree to it.')

        if not (p.get('password') or ''):
            errors.append('Password is required.')
        elif p.get('password') != p.get('confirm_password'):
            errors.append('Passwords do not match.')
        address_problem = email_verify.address_error(p.get('email'))
        if address_problem:
            errors.append(address_problem)
        elif User.objects.filter(email=p.get('email')).exclude(
                verification_status='rejected').exists():
            errors.append('Email already registered.')

        declarations, declared, disability = [], None, ''
        if account_type == 'student':
            errors += _unanswered(p, _REQUIRED_OF_A_STUDENT)
            errors += _unanswered_tes(p, _REQUIRED_AFFIRMATIVE_ANSWERS)
            if not p.get('student_id'):
                errors.append('Student ID is required.')
            elif StudentProfile.objects.filter(
                    student_id=p.get('student_id')).exclude(
                    user__verification_status='rejected').exists():
                errors.append('Student ID already registered.')

            if not (p.get('disability_type') or '').strip():
                errors.append('Disability Type is required — choose "NO" if you are '
                              'not a person with disability.')
            disability, problem = _disability_answer(p)
            if problem:
                errors.append(problem)

            declarations, link_errors = _declared_scholarships(p, request.FILES)
            errors.extend(link_errors)
            errors.extend(_certificate_errors(request.FILES))
            if not any(f'has_scholarship{slot}' in p for slot in DECLARATION_SLOTS):
                errors += _unanswered(p, _REQUIRED_OF_AN_APPLICANT)
                errors += _unanswered_tes(p, _REQUIRED_TES_ANSWERS)
        else:
            errors += _unanswered(p, _REQUIRED_OF_STAFF)
            declared, link_errors = _declared_staff_scholarship(p, request.FILES)
            errors.extend(link_errors)

        if errors:
            return render(request, 'register.html',
                          dict(_register_context(p), errors=errors, post=p))

        _release_rejected_registration(p.get('email'), p.get('student_id'))

        user = User.objects.create_user(
            username=p.get('email'),
            email=p.get('email'),
            password=p.get('password'),
            first_name=p.get('first_name', '').strip(),
            last_name=p.get('last_name', '').strip(),
            role=account_type,
            verification_status='pending',
            email_verified=False,
            terms_version=terms.VERSION,
            terms_accepted_at=timezone.now(),
        )
        email_verify.send_confirmation(user, request)

        if account_type == 'student':
            profile = StudentProfile.objects.create(
                user=user,
                student_id=p.get('student_id'),
                **_registration_profile_fields(p, request.FILES, disability),
            )
            for declaration in declarations:
                ScholarshipLinkRequest.objects.create(student=profile, **declaration)
            if len(declarations) > 1:
                notify.multiple_declarations(profile, declarations)
            return _await_verification(request, user)

        else:
            from .models import StaffProfile
            staff_school = p.get('staff_school', '').strip()
            StaffProfile.objects.create(
                user=user,
                middle_name=p.get('middle_name', '').strip(),
                suffix=p.get('suffix', '').strip(),
                contact_number=p.get('contact_number', '').strip(),
                date_of_birth=p.get('date_of_birth') or None,
                gender=p.get('gender', ''),
                employee_id=p.get('school_id', '').strip(),
                school=staff_school,
                department=p.get('department', '').strip(),
                position=p.get('position', '').strip(),
            )
            if declared:
                from .models import StaffScholarshipDeclaration
                StaffScholarshipDeclaration.objects.create(staff_user=user, **declared)
            from .models import ActivityLog
            ActivityLog.objects.create(
                user=user,
                action=(
                    f"Staff account created — "
                    f"School ID: {p.get('school_id','—')} | "
                    f"School: {staff_school or '—'} | "
                    f"Department: {p.get('department','—')} | "
                    f"Position: {p.get('position','—')} | "
                    f"Contact: {p.get('contact_number','—')}"
                ),
            )
            return _await_verification(request, user)

    return render(request, 'register.html', dict(_register_context(), post={}))


def _tristate(raw, current):
    value = (raw or '').strip().casefold()
    if value == 'yes':
        return True
    if value == 'no':
        return False
    if value == 'unknown':
        return None
    return current


def _positive_int(raw, current):
    text = (raw or '').strip()
    if text == '':
        return None
    if text.isdigit() and int(text) > 0:
        return int(text)
    return current


def _disability_answer(posted):
    from . import disability_list
    value = (posted.get('disability_type') or '').strip()
    if value != disability_list.OTHER:
        return value, ''
    typed = (posted.get('disability_type_other') or '').strip()
    if not typed:
        return '', 'Name the disability you chose "Other" for.'
    return typed, ''


def _disability_fields(posted_value, posted_other, saved):
    from . import disability_list
    options = disability_list.disability_types()
    if posted_value is not None:
        value, other = posted_value, posted_other
    else:
        saved = (saved or '').strip()
        custom = saved if saved and saved not in options else ''
        value, other = (disability_list.OTHER if custom else saved), custom
    return {
        'disabilities': options,
        'other_option': disability_list.OTHER,
        'disability_value': value,
        'disability_other': other,
    }


def _scholarship_records(profile):
    if not profile:
        return []
    records = [{
        'name': app.scholarship.name,
        'type': app.scholarship.type,
        'status': 'Approved',
        'term': ' '.join(x for x in (app.school_year, app.semester) if x),
        'award_number': app.award_number,
        'note': '',
    } for app in Application.objects.filter(student=profile, status='Approved')
        .select_related('scholarship').order_by('-submitted_at')]

    for req in ScholarshipLinkRequest.objects.filter(
            student=profile).exclude(status='Approved').order_by('-submitted_at'):
        records.append({
            'name': req.get_scholarship_type_display(),
            'type': req.scholarship_type,
            'status': req.status,
            'term': req.term_display,
            'award_number': req.award_number,
            'note': req.remarks if req.status == 'Rejected' else
                    'Declared at registration. The SDSO is still verifying your proof.',
        })
    return records


def _parse_gwa(raw):
    try:
        value = float((raw or '').strip())
    except (TypeError, ValueError):
        return None
    return value if 1.0 <= value <= 5.0 else None


def held_scholarship_types(profile):
    if not profile:
        return set()
    held = set(
        Application.objects.filter(student=profile, status='Approved')
        .values_list('scholarship__type', flat=True))
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    held |= set(
        ScholarshipLinkRequest.objects.filter(
            student=profile, status='Approved', term_label=settings_obj.academic_year,
        ).values_list('scholarship_type', flat=True))
    return {t for t in held if t}


def can_hold_alongside(held, wanted):
    return not set(held)


def application_window_reason(stype):
    from django.utils import timezone
    programme = Scholarship.objects.filter(type=stype).first()
    if not programme:
        return ''
    return programme.window_closed_reason(timezone.localdate())


def renewal_window_reason(stype):
    from django.utils import timezone
    programme = Scholarship.objects.filter(type=stype).first()
    if not programme:
        return ''
    return programme.renewal_closed_reason(timezone.localdate())


def scholarship_block_reason(profile, wanted, label):
    shut = application_window_reason(wanted)
    if shut:
        return shut
    held = held_scholarship_types(profile)
    if can_hold_alongside(held, wanted):
        return ''
    if wanted in held:
        return f'You already hold the {label}. There is nothing to apply for.'
    from .models import SCHOLARSHIP_TYPE_CHOICES
    display = dict(SCHOLARSHIP_TYPE_CHOICES)
    names = ', '.join(sorted(display.get(t, t) for t in held))
    return (f'You are already enrolled in {names}. Each programme is held on '
            'its own — a scholar may not be on two at once.')


def _is_enrolled(profile):
    return bool(held_scholarship_types(profile))


def _system_settings():
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return settings_obj


def _validate_proof(uploaded, settings_obj):
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
    from .constants import EDITABLE_APPLICATION_STATUSES
    profile = StudentProfile.objects.filter(user=request.user).first()
    editing = Application.objects.filter(
        student=profile, status__in=EDITABLE_APPLICATION_STATUSES
    ).select_related('scholarship').order_by('-submitted_at', '-pk').first() if profile else None
    blocked_reason = scholarship_block_reason(
        profile, 'Academic', 'Academic Scholarship')
    if blocked_reason:
        return render(request, 'student/apply_academic.html', {
            'profile': profile, 'blocked': True,
            'blocked_reason': blocked_reason,
            'classification': '', 'eligible': False,
        })
    if request.method == 'POST':
        scholarship = Scholarship.objects.filter(type='Academic').first()
        if scholarship and profile:
            declared = _parse_gwa(request.POST.get('gwa'))
            if declared is not None:
                profile.gwa = declared
                profile.save(update_fields=['gwa'])
            if editing:
                app = editing
                app.form_data = request.POST.dict()
                app.status = 'Pending Validation'
                app.remarks = ''
                app.save()
            else:
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
                    app.documents.filter(name=label).delete()
                    ApplicationDocument.objects.create(application=app, name=label, file=uploaded)
        return redirect('/student/applications/')
    from .constants import (
        COLLEGE_SCHOLAR_MAX_GWA, UNIVERSITY_SCHOLAR_MAX_GWA, academic_classification,
    )
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    gwa = profile.gwa if profile else 0
    classification = academic_classification(gwa)
    term = SystemSettings.parse_label(settings_obj.academic_year)
    return render(request, 'student/apply_academic.html', {
        'profile': profile,
        'editing': editing,
        'submitted_documents': list(editing.documents.all()) if editing else [],
        'active_school_year': term['sy'],
        'active_semester': term['semester'],
        'classification': classification,
        'eligible': classification in ('University Scholar', 'College Scholar'),
        'enrolled': _is_enrolled(profile),
        'university_max_gwa': UNIVERSITY_SCHOLAR_MAX_GWA,
        'college_max_gwa': COLLEGE_SCHOLAR_MAX_GWA,
    })
    


@login_required(login_url='/login/')
def student_applications(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    applications = Application.objects.filter(student=profile).select_related('scholarship') if profile else Application.objects.none()
    return render(request, 'student/applications.html', {
        'applications': applications,
        'enrolled': _is_enrolled(profile),
    })


def pending_declarations():
    return (ScholarshipLinkRequest.objects
            .select_related('student__user', 'reviewed_by', 'matched_archive',
                            *STUDENT_DETAILS)
            .filter(status='Pending', filed_in_portal=True)
            .order_by('submitted_at', 'pk'))


def declarable_types(profile):
    from .constants import DECLARABLE_SCHOLARSHIP_TYPES
    held = held_scholarship_types(profile) if profile else set()
    return [(value, label) for value, label in DECLARABLE_SCHOLARSHIP_TYPES
            if can_hold_alongside(held, value)]


def declaration_blocked_reason(profile):
    if not profile:
        return ('Your student record is not set up yet. Open My Profile and '
                'fill it in first — the office matches a scholarship to their '
                'own records by your name and student number, and cannot check '
                'one that has neither.')

    waiting = (ScholarshipLinkRequest.objects
               .filter(student=profile, status='Pending')
               .order_by('submitted_at').first())
    if waiting:
        return (f'You have already told the SDSO about the '
                f'{waiting.get_scholarship_type_display()} and they are still '
                'checking it. Wait for that decision — sending the same award '
                'twice puts one thing in front of them twice.')

    if not declarable_types(profile):
        from .models import SCHOLARSHIP_TYPE_CHOICES
        labels = dict(SCHOLARSHIP_TYPE_CHOICES)
        named = ', '.join(sorted(labels.get(t, t)
                                 for t in held_scholarship_types(profile)))
        return (f'This account already holds the {named}. Every programme here '
                'is exclusive, so there is nothing to add beside it. If that is '
                'no longer right — an award that ended, or one recorded in '
                'error — the SDSO corrects it from their side.')
    return ''


@login_required(login_url='/login/')
def student_notifications(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    notifications = Notification.objects.filter(student=profile).order_by('-created_at') if profile else Notification.objects.none()
    return render(request, 'student/notifications.html', {'notifications': notifications, 'enrolled': _is_enrolled(profile)})


def _renewable_programmes(profile):
    from .models import SCHOLARSHIP_TYPE_CHOICES
    labels = dict(SCHOLARSHIP_TYPE_CHOICES)
    programmes = []
    for stype in sorted(held_scholarship_types(profile)):
        shut = renewal_window_reason(stype)
        programmes.append({
            'type': stype,
            'label': labels.get(stype, stype),
            'open': not shut,
            'closed_reason': shut,
        })
    return programmes


@login_required(login_url='/login/')
def student_renewal_academic(request):
    from .models import SystemSettings
    profile = StudentProfile.objects.filter(user=request.user).first()
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    programmes = _renewable_programmes(profile)
    open_programmes = [p for p in programmes if p['open']]

    renewals = (AcademicRenewal.objects.filter(student=profile)
                .order_by('-submitted_at') if profile else [])

    def page(**extra):
        context = {
            'profile': profile,
            'programmes': programmes,
            'open_programmes': open_programmes,
            'multiple': len(open_programmes) > 1,
            'renewals': renewals,
            'semester': parsed['semester'],
            'academic_year': parsed['sy'],
            'enrolled': _is_enrolled(profile),
        }
        context.update(extra)
        return render(request, 'student/renewal_academic.html', context)

    if programmes and not open_programmes:
        return page(blocked=True, blocked_reason=' '.join(
            f"{p['label']}: {p['closed_reason']}" for p in programmes))

    if request.method == 'POST' and profile:
        cog = request.FILES.get('certificate_of_grades')
        coe = request.FILES.get('certificate_of_enrollment')
        errors = []

        posted = (request.POST.get('scholarship_type') or '').strip()
        chosen = next((p for p in open_programmes if p['type'] == posted), None)
        if chosen is None:
            if posted:
                errors.append('That is not a programme you hold with renewals open. '
                              'Pick one of the programmes listed.')
            elif len(open_programmes) == 1:
                chosen = open_programmes[0]
            elif not open_programmes:
                errors.append('A renewal continues a scholarship you already '
                              'hold, and there is none on your record yet.')
            else:
                errors.append('Choose which scholarship you are renewing.')

        if not cog:
            errors.append('Certificate of Grades is required.')
        if not coe:
            errors.append('Certificate of Enrollment is required.')
        if errors:
            return page(errors=errors)

        pending = AcademicRenewal.objects.filter(
            student=profile, status='Pending', term_label=settings_obj.academic_year,
            scholarship_type=chosen['type'],
        ).order_by('-submitted_at').first()
        if pending:
            pending.certificate_of_grades = cog
            pending.certificate_of_enrollment = coe
            pending.save(update_fields=['certificate_of_grades', 'certificate_of_enrollment'])
        else:
            AcademicRenewal.objects.create(
                student=profile, certificate_of_grades=cog,
                certificate_of_enrollment=coe, scholarship_type=chosen['type'])
        return redirect('/student/renewal/academic/?submitted=1')

    editing = {}
    if profile:
        for pending in AcademicRenewal.objects.filter(
                student=profile, status='Pending',
                term_label=settings_obj.academic_year).order_by('submitted_at'):
            editing[pending.scholarship_type] = pending
    replacing = (len(open_programmes) == 1
                 and open_programmes[0]['type'] in editing)
    return page(editing=editing, replacing=replacing,
                submitted=request.GET.get('submitted'))


@login_required(login_url='/login/')
def student_profile(request):
    profile = StudentProfile.objects.filter(user=request.user).first()
    errors = []
    saved = False
    declared_count = 0
    if request.method == 'POST' and profile:
        p = request.POST
        u = profile.user
        if not profile.middle_name:
            profile.middle_name = p.get('middle_name', '').strip()
        profile.suffix = p.get('suffix', profile.suffix).strip()
        if not profile.civil_status:
            profile.civil_status = p.get('civil_status', profile.civil_status)
        if not profile.birth_place:
            profile.birth_place = p.get('birth_place', profile.birth_place).strip()
        profile.family_income = float(p.get('family_income', profile.family_income) or profile.family_income)
        profile.indigenous_group = p.get('indigenous_group', profile.indigenous_group)
        disability, problem = _disability_answer(p)
        if problem:
            errors.append(problem)
        else:
            profile.disability_type = disability
        if not (profile.elementary and profile.highschool and profile.last_school):
            profile.elementary = p.get('elementary', profile.elementary)
            profile.highschool = p.get('highschool', profile.highschool)
            profile.last_school = p.get('last_school', profile.last_school)
        profile.highschool_is_public = _tristate(
            p.get('highschool_is_public'), profile.highschool_is_public)
        profile.is_from_depressed_area = _tristate(
            p.get('is_from_depressed_area'), profile.is_from_depressed_area)
        if not (profile.father_last_name and profile.father_first_name
                and profile.mother_last_name and profile.mother_first_name):
            for parent in ('father', 'mother'):
                for part in ('last_name', 'first_name', 'middle_name'):
                    field = f'{parent}_{part}'
                    setattr(profile, field, p.get(field, getattr(profile, field)).strip())
            profile.father_occupation = p.get('father_occupation', profile.father_occupation)
            profile.mother_occupation = p.get('mother_occupation', profile.mother_occupation)
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
        profile.is_solo_parent_dependent = _tristate(
            p.get('is_solo_parent_dependent'), profile.is_solo_parent_dependent)
        raw_shs = p.get('shs_gpa', '').strip()
        if raw_shs:
            try: profile.shs_gpa = float(raw_shs)
            except ValueError: pass
        raw_total = p.get('suc_exam_total', '').strip()
        if raw_total:
            try:
                total = float(raw_total)
                profile.suc_exam_total = total if total > 0 else None
            except ValueError:
                pass
        else:
            profile.suc_exam_total = None
        raw_suc = p.get('suc_exam_score', '').strip()
        if raw_suc:
            try: profile.suc_exam_score = float(raw_suc)
            except ValueError: pass
        if profile.suc_exam_score is not None and not profile.suc_exam_total:
            errors.append('SUC Admission Exam Total is required when a score is '
                          'given — 42 out of 50 and 42 out of 100 are not the '
                          'same result, and the rules read the percentage.')
        elif (profile.suc_exam_score is not None
              and profile.suc_exam_score > profile.suc_exam_total):
            errors.append('SUC Admission Exam Score cannot be higher than the total.')
        profile.is_tes_beneficiary = 'is_tes_beneficiary' in p
        if request.FILES.get('shs_gpa_cert'):
            profile.shs_gpa_cert = request.FILES['shs_gpa_cert']
        if request.FILES.get('suc_exam_cert'):
            profile.suc_exam_cert = request.FILES['suc_exam_cert']
        if request.FILES.get('photo'):
            u.photo = request.FILES['photo']
            u.save(update_fields=['photo'])
        if not (profile.barangay and profile.municipality and profile.province):
            profile.barangay = p.get('barangay', profile.barangay)
            profile.municipality = p.get('municipality', profile.municipality)
            profile.province = p.get('province', profile.province)

        declarations = []
        if not declaration_blocked_reason(profile):
            declarations, declaration_errors = _declared_scholarships(
                p, request.FILES)
            errors.extend(declaration_errors)
            allowed = dict(declarable_types(profile))
            for declared in declarations:
                if declared['scholarship_type'] not in allowed:
                    from .models import SCHOLARSHIP_TYPE_CHOICES
                    label = dict(SCHOLARSHIP_TYPE_CHOICES).get(
                        declared['scholarship_type'], declared['scholarship_type'])
                    errors.append(f'The {label} cannot be added alongside what '
                                  'this account already holds. Reload this page '
                                  'to see what is still open to you.')

        if not errors:
            profile.save()
            saved = True
            for declared in declarations:
                ScholarshipLinkRequest.objects.create(
                    student=profile, filed_in_portal=True, **declared)
            if declarations:
                notify.scholarship_added(profile, declarations)
                declared_count = len(declarations)
    import json
    from .constants import CIVIL_STATUSES
    from .models import CHED_TIER_CHOICES
    address_locked = bool(profile and profile.barangay and profile.municipality and profile.province)
    civil_status_locked = bool(profile and profile.civil_status)
    birth_place_locked = bool(profile and profile.birth_place)
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
        'birth_place_locked': birth_place_locked,
        'education_locked': education_locked,
        'family_locked': family_locked,
        'civil_statuses': CIVIL_STATUSES,
        'scholarships_held': _scholarship_records(profile),
        'declared_count': declared_count,
        'scholarship_blocked_reason': declaration_blocked_reason(profile),
        'scholarship_types': declarable_types(profile),
        'ched_tiers': CHED_TIER_CHOICES,
        'declaration_slots': _declaration_slots(request.POST if errors else None),
        'max_upload_mb': _system_settings().max_file_size_mb or 5,
        **_disability_fields(
            request.POST.get('disability_type') if errors else None,
            request.POST.get('disability_type_other', '') if errors else '',
            profile.disability_type if profile else ''),
    })


def _change_own_password(request, user):
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    from .models import ActivityLog

    current = request.POST.get('current_password') or ''
    new = request.POST.get('new_password') or ''
    confirm = request.POST.get('new_password_confirm') or ''

    if not (current or new or confirm):
        return []

    errors = []
    if not user.check_password(current):
        errors.append('Your current password is not right. '
                      'Passwords are case-sensitive.')
    if not new:
        errors.append('Enter the new password you want.')
    elif new != confirm:
        errors.append('The two new passwords do not match.')
    else:
        try:
            validate_password(new, user)
        except ValidationError as bad:
            errors.extend(bad.messages)
    if errors:
        return errors

    user.set_password(new)
    user.save(update_fields=['password'])
    update_session_auth_hash(request, user)
    ActivityLog.objects.create(user=user, action='Changed their own password')
    return []


def _partner_office(user):
    if not getattr(user, 'is_authenticated', False) or user.role != 'partner':
        return None
    office = user.partner_office
    if office is None or not office.is_active:
        return None
    return office


def _partner_required(view_fn):
    from functools import wraps

    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        office = _partner_office(request.user)
        if office is None:
            return redirect('/login/')
        return view_fn(request, office, *args, **kwargs)
    return wrapper


def _vpsea_required(view_fn):
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'vpsea':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper


def _safe_next(request, fallback):
    from django.utils.http import url_has_allowed_host_and_scheme

    wanted = request.GET.get('next') or ''
    if wanted and url_has_allowed_host_and_scheme(
            wanted, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return wanted
    return fallback


def _active_term():
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return SystemSettings.parse_label(settings_obj.academic_year)


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
    ActivityLog.objects.create(
        user=request.user,
        action=f'{label} for {programme.name}: {state}')
    return redirect(f'{back}{joiner}saved=window')


@_vpsea_required
def vpsea_affirmative_applications(request):
    from .constants import DECIDED_APPLICATION_STATUSES
    from .models import AffirmativeStaffApplication, Application
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
                acad_app.status = new_status
                acad_app.remarks = remarks
                acad_app.save()
                notify.decision(
                    acad_app.student, f'Your {acad_app.scholarship.name} application',
                    new_status, remarks, link='/student/applications/',
                )
            except Application.DoesNotExist:
                pass
            return redirect('/vpsea/affirmative/?tab=academic')
        else:
            try:
                aff_app = AffirmativeStaffApplication.objects.get(id=app_id)
                if aff_app.status in DECIDED_APPLICATION_STATUSES:
                    return redirect(f'/vpsea/affirmative/?tab={tab}&error=' + quote(
                        f'{aff_app.full_name} was already decided '
                        f'({aff_app.status}). A decision is made once.'))
                aff_app.status = new_status
                aff_app.remarks = remarks
                aff_app.save()
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
            except AffirmativeStaffApplication.DoesNotExist:
                pass
            return redirect(f'/vpsea/affirmative/?tab={tab}')

    tab = request.GET.get('tab', 'academic')
    if tab not in ('academic', 'staff'):
        tab = 'academic'
    academic_apps = (
        Application.objects
        .select_related('student__user', 'scholarship', *STUDENT_DETAILS)
        .prefetch_related('documents')
        .exclude(scholarship__type__in=['Staff'])
        .order_by('-submitted_at')
    )
    staff_apps = AffirmativeStaffApplication.objects.filter(
        qualified_for='Staff').select_related(*STAFF_APPLICATION_DETAILS).order_by('-submitted_at')
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
    from .models import Application, AcademicRenewal, AffirmativeStaffApplication, SystemSettings
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
        'pending_staff': AffirmativeStaffApplication.objects.filter(qualified_for='Staff', status='Pending Validation').count(),
        'pending_affirmative': AffirmativeStaffApplication.objects.filter(qualified_for='Affirmative', status='Pending Validation').count(),
        'active_sy_display': f"{active_sy} — {active_semester}",
    }
    return render(request, 'vpsea/dashboard.html', ctx)


@_vpsea_required
def vpsea_renewals(request):
    if request.method == 'POST':
        from .models import SystemSettings
        if request.POST.get('window') == 'renewals':
            return _save_window(
                request, Scholarship.objects.filter(type='Academic').first(),
                'renewals', '/vpsea/renewals/')
        renewal_id = request.POST.get('renewal_id')
        new_status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        AcademicRenewal.objects.filter(id=renewal_id).update(status=new_status, remarks=remarks)
        reviewed = AcademicRenewal.objects.select_related('student__user', *STUDENT_DETAILS).filter(id=renewal_id).first()
        if reviewed:
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
    renewals = AcademicRenewal.objects.select_related('student__user', *STUDENT_DETAILS).order_by('-submitted_at')
    return render(request, 'vpsea/renewals.html', {
        'renewals': renewals,
        'approved_count': renewals.filter(status='Approved').count(),
        'pending_count': renewals.filter(status='Pending').count(),
        'saved': request.GET.get('saved'),
        'error': request.GET.get('error'),
        **_window_card_context(
            Scholarship.objects.filter(type='Academic').first(), 'renewals'),
    })


def _archive_candidates(req, label=None):
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


def declared_scholarships(profile):
    if not profile:
        return []
    return list(ScholarshipLinkRequest.objects
                .select_related('student__user', *STUDENT_DETAILS)
                .filter(student=profile, status='Pending', filed_in_portal=False)
                .order_by('submitted_at', 'pk'))


def approve_declared_scholarship(req, reviewer, archive=None, remarks='', tier=''):
    from .models import (CHED_TIER_CHOICES, Notification, ActivityLog,
                         SystemSettings)
    from django.utils import timezone

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    profile = req.student
    label = req.get_scholarship_type_display()

    scholarship = Scholarship.objects.filter(type=req.scholarship_type).first()
    if not scholarship:
        return None, (f'No {req.scholarship_type} program is configured under '
                      'Scholarship Programs, so the award cannot be recorded.')

    form_data = {}
    if req.scholarship_type == 'CHED':
        tier = tier or req.award_tier
        if tier not in [t for t, _ in CHED_TIER_CHOICES]:
            return None, ('Choose Full or Half Merit before verifying a CHED '
                          'scholar — the masterlists report the two separately.')
        req.award_tier = tier
        form_data['scholar_type'] = dict(CHED_TIER_CHOICES)[tier]

    if archive is not None:
        form_data['imported_from'] = archive.imported_from

    award_fields = {
        'source': 'link',
        'school_year': parsed['sy'],
        'semester': parsed['semester'],
        'award_number': req.award_number or (archive.award_number if archive else ''),
        'congress_district': archive.congress_district if archive else '',
        'claimed_archive': archive,
    }

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

    if archive is not None:
        archive.claimed_by = profile
        archive.save(update_fields=['claimed_by'])
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
    req.reviewed_by = reviewer
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
        user=reviewer,
        action=(f'Verified the {label} declared by {profile.student_id}'
                + (f' (merged imported row #{archive.id})' if archive
                   else ' (no imported row matched)')),
    )
    return app, ''


def reject_declared_scholarship(req, reviewer, remarks):
    from .models import Notification, ActivityLog
    from django.utils import timezone

    label = req.get_scholarship_type_display()
    req.status = 'Rejected'
    req.remarks = remarks
    req.reviewed_by = reviewer
    req.reviewed_at = timezone.now()
    req.save()
    Notification.objects.create(
        student=req.student, type='warning',
        title=f'{label} could not be verified',
        body=f'The SDSO could not verify the {label} you declared. Reason: {remarks}',
    )
    ActivityLog.objects.create(
        user=reviewer,
        action=f'Rejected the {label} declared by {req.student.student_id}',
    )


UNAWARDED_TAB = 'No Scholarship'


def _archive_back(stype, tier=''):
    from urllib.parse import quote

    url = f'/vpsea/archives/?type={quote(stype)}'
    return url + (f'&tier={tier}' if tier in CHED_ARCHIVE_TIERS else '')


CHED_ARCHIVE_TIERS = ('Full', 'Half')


def declared_staff_scholarship(user):
    from .models import StaffScholarshipDeclaration
    if not user:
        return None
    return (StaffScholarshipDeclaration.objects
            .filter(staff_user=user, status='Pending')
            .order_by('-submitted_at').first())


def approve_declared_staff_scholarship(decl, reviewer, remarks=''):
    from django.utils import timezone
    from .models import (ActivityLog, AffirmativeStaffApplication, StaffProfile,
                         SystemSettings)

    user = decl.staff_user
    staff = StaffProfile.objects.filter(user=user).first()
    if staff is None:
        return None, ('That account has no staff profile, so the award has '
                      'nowhere to be recorded.')

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)

    app = AffirmativeStaffApplication.objects.filter(
        email=user.email, qualified_for='Staff',
        school_year=parsed['sy'], semester=parsed['semester'],
    ).first()
    if app is None:
        app = AffirmativeStaffApplication(email=user.email)

    app.full_name = user.get_full_name()
    app.qualified_for = 'Staff'
    app.status = 'Approved'
    app.remarks = remarks
    app.school_year = parsed['sy']
    app.semester = parsed['semester']
    app.term_label = settings_obj.academic_year
    app.barangay = staff.barangay
    app.municipality = staff.municipality
    app.province = staff.province
    app.save()

    app.contact_number = staff.contact_number
    app.date_of_birth = staff.date_of_birth
    app.gender = staff.gender
    app.is_nsu_staff = True
    app.is_nsu_dependent = False
    app.staff_employee_id = staff.employee_id
    app.employment_status = staff.employment_status
    app.designation = staff.designation
    app.department = staff.department
    app.position = staff.position
    app.school = staff.school
    app.save()

    decl.status = 'Approved'
    decl.remarks = remarks
    decl.reviewed_by = reviewer
    decl.reviewed_at = timezone.now()
    decl.linked_application = app
    decl.save()

    ActivityLog.objects.create(
        user=reviewer,
        action=(f'Verified the BiPSU Staff Scholarship declared by '
                f'{user.get_full_name() or user.email} — recorded as an award '
                f"for {parsed['sy']} {parsed['semester']}."),
    )
    return app, ''


def reject_declared_staff_scholarship(decl, reviewer, remarks):
    from django.utils import timezone
    from .models import ActivityLog

    decl.status = 'Rejected'
    decl.remarks = remarks
    decl.reviewed_by = reviewer
    decl.reviewed_at = timezone.now()
    decl.save()
    ActivityLog.objects.create(
        user=reviewer,
        action=(f'Turned down the BiPSU Staff Scholarship declared by '
                f'{decl.staff_user.get_full_name() or decl.staff_user.email} — {remarks}'),
    )


def _unawarded_rows(term_label):
    from .constants import academic_classification

    awarded = Application.objects.filter(
        status='Approved', term_label=term_label,
    ).values_list('student_id', flat=True)

    students = (
        StudentProfile.objects
        .exclude(id__in=awarded)
        .filter(user__verification_status='approved')
        .select_related('user', *StudentProfile.DETAIL_RELATIONS)
        .prefetch_related('applications__scholarship')
        .order_by('user__last_name', 'user__first_name')
    )

    rows = []
    for profile in students:
        apps = sorted(profile.applications.all(),
                      key=lambda a: (a.submitted_at or date.min, a.pk),
                      reverse=True)
        latest = apps[0] if apps else None
        if latest is None:
            state = 'never'
        elif latest.status == 'Rejected':
            state = 'rejected'
        else:
            state = 'pending'
        rows.append({
            'profile': profile,
            'latest': latest,
            'state': state,
            'classification': academic_classification(profile.gwa),
        })
    return rows


def _scholar_groups(stype, groups, portal='vpsea', override=None):
    from . import scholar_columns
    from .models import Scholarship

    programme = Scholarship.objects.filter(type=stype).first()
    columns = scholar_columns.resolve(programme, stype, portal, override=override)
    built = []
    for title, records, empty in groups:
        records = list(records)
        built.append({
            'title': title,
            'rows': scholar_columns.rows_for(records, columns),
            'empty': empty,
        })
    return {
        'columns': columns,
        'scholar_groups': built,
        'has_custom_columns': any(c['custom'] for c in columns),
    }


def _archive_tabs(archive_types, active_type, active_tier):
    from urllib.parse import quote

    from .models import CHED_TIER_CHOICES, SCHOLARSHIP_GROUPS, Scholarship

    funders = dict(Scholarship.objects.values_list('type', 'group'))
    tier_labels = dict(CHED_TIER_CHOICES)
    order = [key for key, _label in SCHOLARSHIP_GROUPS] + ['other']
    names = {**dict(SCHOLARSHIP_GROUPS), 'other': 'Other'}

    entries = []
    for stype in archive_types:
        group = funders.get(stype, 'other')
        if stype == 'CHED':
            for tier in CHED_ARCHIVE_TIERS:
                entries.append({
                    'label': f'CHED {tier} Merit',
                    'note': tier_labels.get(tier, ''),
                    'href': f'/vpsea/archives/?type=CHED&tier={tier}',
                    'group': group,
                    'active': active_type == 'CHED' and active_tier == tier,
                })
            continue
        entries.append({
            'label': stype,
            'note': '',
            'href': f'/vpsea/archives/?type={quote(stype)}',
            'group': group,
            'active': stype == active_type,
        })

    grouped = []
    for key in order:
        tabs = [e for e in entries if e['group'] == key]
        if tabs:
            grouped.append({'label': names[key], 'tabs': tabs})
    return grouped


def _archive_terms(stype, active_label):
    from .models import ScholarListImport

    labels = list(
        ScholarListImport.objects.filter(scholarship_type=stype)
        .values_list('term_label', flat=True).distinct().order_by('-term_label')
    )
    if active_label not in labels:
        labels.insert(0, active_label)
    return labels


def _archive_term(request, stype, active_label):
    labels = _archive_terms(stype, active_label)
    chosen = request.GET.get('sy', active_label)
    return labels, chosen if chosen in labels else active_label


def _archive_records(stype, term_label, tier=None):
    from .models import ImportedScholar

    imported_rows = list(ImportedScholar.objects.filter(
        scholarship_type=stype, term_label=term_label, claimed_by__isnull=True,
    ).order_by('last_name', 'first_name'))

    if stype in ('Affirmative', 'Staff'):
        scholars = list(AffirmativeStaffApplication.objects.filter(
            status='Approved', qualified_for=stype
        ).select_related(*STAFF_APPLICATION_DETAILS).order_by('full_name'))
        return [(None, scholars + imported_rows,
                 f'No approved {stype} scholars yet.')]

    awards = Application.objects.filter(
        status='Approved', scholarship__type=stype, term_label=term_label,
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS)

    if stype == 'CHED':
        full, half = split_ched(awards.order_by('student__user__last_name'))
        imported_half = [r for r in imported_rows if r.award_tier == 'Half']
        imported_full = [r for r in imported_rows if r.award_tier != 'Half']
        blocks = [
            ('Full', 'Full Merit / Full Scholar', list(full) + imported_full,
             'No approved CHED full scholars yet.'),
            ('Half', 'Half Merit / Partial Scholar', list(half) + imported_half,
             'No approved CHED half scholars yet.'),
        ]
        if tier in CHED_ARCHIVE_TIERS:
            _key, _title, records, empty = next(
                b for b in blocks if b[0] == tier)
            return [(None, records, empty)]
        return [(title, records, empty) for _key, title, records, empty in blocks]

    scholars = list(awards.order_by('student__user__last_name').distinct())
    return [(None, scholars + imported_rows,
             f'No approved {stype} scholars yet.')]


@_vpsea_required
def vpsea_archives(request):
    from .models import ScholarListImport, SystemSettings, ActivityLog
    stype = request.GET.get('type', 'Academic')
    tier = request.GET.get('tier', '')
    if stype == 'CHED' and tier not in CHED_ARCHIVE_TIERS:
        tier = CHED_ARCHIVE_TIERS[0]
    elif stype != 'CHED':
        tier = ''
    base_types = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    db_types = list(Scholarship.objects.values_list('type', flat=True).distinct())
    archive_types = base_types + [t for t in db_types if t not in base_types] + [UNAWARDED_TAB]
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    parsed = SystemSettings.parse_label(active_label)
    active_sy = parsed['sy']
    active_semester = parsed['semester']

    history = ScholarListImport.objects.filter(scholarship_type=stype).order_by('-created_at')
    all_labels, selected_label = _archive_term(request, stype, active_label)

    selected_parsed = SystemSettings.parse_label(selected_label)
    selected_sy = selected_parsed['sy']

    next_label = settings_obj.next_label()
    active_display = f"{active_sy} — {active_semester}"
    all_sy_display = []
    for lbl in all_labels:
        p = SystemSettings.parse_label(lbl)
        all_sy_display.append((lbl, f"{p['sy']} — {p['semester']}"))

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
        'archive_tabs': _archive_tabs(archive_types, stype, tier),
        'active_tier': tier,
        'active_tab_label': f'CHED {tier} Merit' if tier else stype,
        'bipsu_schools': BIPSU_SCHOOLS,
        'bipsu_courses_json': _json.dumps(BIPSU_COURSES),
        'active_type': stype,
        'history': history,
        'all_sy': all_labels,
        'all_sy_display': all_sy_display,
        'selected_sy': selected_label,
        'selected_sy_display': f"{selected_sy} — {selected_parsed['semester']}",
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
            (4, '2×2 ID Photo', 'Recent 2×2 ID photo with white background.', 'doc_id_photo'),
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

    groups = _archive_records(stype, selected_label, tier)
    return render(request, 'vpsea/archives.html', {
        **base_ctx,
        **_scholar_groups(stype, groups),
        'total': sum(len(records) for _title, records, _empty in groups),
    })


@_vpsea_required
def vpsea_archive_add(request):
    from .models import (Application, Scholarship, StudentProfile, User,
                         AffirmativeStaffApplication, SystemSettings,
                         ApplicationDocument, CHED_TIER_CHOICES)
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    p = request.POST
    f = request.FILES
    stype = p.get('scholarship_type', 'Academic')
    tier = p.get('tier', '') if stype == 'CHED' else ''
    if tier not in CHED_ARCHIVE_TIERS:
        tier = ''
    back = f'/vpsea/archives/?type={stype}' + (f'&tier={tier}' if tier else '')
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    active_sy = parsed['sy']
    active_semester = parsed['semester']

    wants_account = p.get('create_account') == 'yes'
    supplied_email = p.get('email', '').strip()

    if wants_account:
        missing = []
        if not supplied_email:
            missing.append('an email address')
        if not p.get('student_id', '').strip():
            missing.append('a student number')
        if missing:
            from urllib.parse import quote
            return redirect(f'{back}&error=' + quote(
                'Creating an account needs ' + ' and '.join(missing) + '. The '
                'address is where the scholar is emailed, and the student number '
                'is their first password. Choose "Just an import" to record this '
                'scholar without an account.'))

    if not wants_account:
        from .models import ImportedScholar
        try:
            year_level = int(p.get('year_level', 0) or 0)
        except (TypeError, ValueError):
            year_level = 0
        try:
            gwa = float(p.get('gwa', 0) or 0)
        except (TypeError, ValueError):
            gwa = 0.0
        ImportedScholar.objects.create(
            scholarship_type=stype,
            term_label=settings_obj.academic_year,
            last_name=p.get('last_name', '').strip(),
            first_name=p.get('first_name', '').strip(),
            middle_name=p.get('middle_name', '').strip(),
            gender=p.get('gender', ''),
            course=p.get('course', ''),
            year_level=year_level,
            gwa=gwa,
            student_id=p.get('student_id', '').strip(),
            award_number=p.get('award_number', ''),
            congress_district=p.get('congress_district', ''),
            barangay=p.get('barangay', ''),
            municipality=p.get('municipality', ''),
            province=p.get('province', ''),
            award_tier=tier,
            imported_from='Added by SDSO',
        )
        return redirect(f'{back}&added=1')

    if stype in ('Affirmative', 'Staff'):
        full_name = f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip()
        email = supplied_email
        if not email:
            email = f"{p.get('student_id','').strip() or full_name.replace(' ','_').lower()}_{stype.lower()}@bipsu.edu.ph"
            base = email
            counter = 1
            while AffirmativeStaffApplication.objects.filter(email=email).exists():
                email = f"{base.split('@')[0]}_{counter}@bipsu.edu.ph"
                counter += 1
        AffirmativeStaffApplication.objects.create(
            full_name=full_name,
            email=email,
            contact_number=p.get('contact_number', ''),
            barangay=p.get('barangay', ''),
            municipality=p.get('municipality', ''),
            province=p.get('province', ''),
            date_of_birth=p.get('date_of_birth') or None,
            gender=p.get('gender', ''),
            course=p.get('course', ''),
            year_level=int(p.get('year_level', 1) or 1),
            student_id=p.get('student_id', ''),
            qualified_for=stype,
            status='Approved',
            is_nsu_staff=(stype == 'Staff'),
        )
    else:
        email = supplied_email
        student_id = p.get('student_id', '').strip()
        if not email:
            email = f"{student_id}@bipsu.edu.ph"
        user = User.objects.filter(email=email).first()
        account_created = False
        if not user:
            user = User.objects.create_user(
                username=email, email=email,
                password=student_id or 'bipsu1234',
                first_name=p.get('first_name', ''),
                last_name=p.get('last_name', ''),
                role='student',
            )
            account_created = True
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
            if tier:
                form_data['scholar_type'] = dict(CHED_TIER_CHOICES)[tier]
            if stype == 'Academic':
                form_data.update({
                    'elementary': p.get('elementary', ''),
                    'highschool': p.get('highschool', ''),
                    'last_school': p.get('last_school', ''),
                })
                parent_fields = [
                    'father_last_name', 'father_first_name', 'father_middle_name',
                    'father_occupation', 'mother_last_name', 'mother_first_name',
                    'mother_middle_name', 'mother_occupation',
                ]
                changed = []
                for field in parent_fields:
                    value = p.get(field, '').strip()
                    if value:
                        setattr(profile, field, value)
                        changed.append(field)
                for field in ('elementary', 'highschool', 'last_school'):
                    value = p.get(field, '').strip()
                    if value:
                        setattr(profile, field, value)
                        changed.append(field)
                if changed:
                    profile.save(update_fields=changed)
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
        if account_created and supplied_email:
            notify.notify(
                user, 'Your SRMS account is ready',
                'The VPSEA office has added you to the Scholarship Records '
                'Management System.\n\n'
                f'Sign in with this email address. Your initial password is your '
                f'student number ({student_id}). Contact the VPSEA office to have '
                'it changed.',
                tone='success',
            )
    return redirect(f'{back}&added=1')


def _apply_student_record_edits(profile, p):
    from .models import StudentProfile

    user = profile.user
    new_sid = (p.get('student_id') or '').strip()
    if (new_sid and new_sid != profile.student_id
            and StudentProfile.objects.filter(student_id=new_sid).exclude(pk=profile.pk).exists()):
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
def vpsea_student_record_delete(request, pk):
    from .models import ActivityLog, StudentProfile
    from urllib.parse import quote
    back = f'/vpsea/archives/?type={quote(UNAWARDED_TAB)}'
    if request.method != 'POST':
        return redirect(back)
    profile = StudentProfile.objects.select_related('user').filter(pk=pk).first()
    if not profile:
        return redirect(back)
    who = profile.user.get_full_name() or profile.student_id
    sid = profile.student_id
    profile.user.delete()
    ActivityLog.objects.create(
        user=request.user,
        action=f'Deleted the student record for {who} ({sid})',
    )
    return redirect(f'{back}&deleted=1')


@_vpsea_required
def vpsea_archive_edit(request, pk):
    from .models import Application, AffirmativeStaffApplication
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    p = request.POST
    stype = p.get('scholarship_type', 'Academic')
    back = _archive_back(stype, p.get('tier', ''))
    is_aff = stype in ('Affirmative', 'Staff')

    if is_aff:
        try:
            obj = AffirmativeStaffApplication.objects.get(pk=pk)
        except AffirmativeStaffApplication.DoesNotExist:
            return redirect(back)
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
        new_pw = (p.get('new_password') or '').strip()
        if new_pw:
            account = User.objects.filter(email=obj.email).first()
            if not account:
                from urllib.parse import quote
                return redirect(
                    f'/vpsea/archives/?type={stype}&error=' + quote(
                        'This scholar has no login account, so the password '
                        'cannot be reset.')
                )
            account.set_password(new_pw)
            account.save()
        obj.save()
    else:
        try:
            app = Application.objects.select_related('student__user', *STUDENT_DETAILS).get(pk=pk)
        except Application.DoesNotExist:
            return redirect(back)
        error = _apply_student_record_edits(app.student, p)
        if error:
            from urllib.parse import quote
            return redirect(f'{back}&error={quote(error)}')
        if p.get('award_number') is not None:
            app.award_number = p.get('award_number')
        if p.get('congress_district') is not None:
            app.congress_district = p.get('congress_district')
        app.save()
    return redirect(f'{back}&edited=1')


@_vpsea_required
def vpsea_archive_delete(request, pk):
    from .models import Application, AffirmativeStaffApplication
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('scholarship_type', 'Academic')
    back = _archive_back(stype, request.POST.get('tier', ''))
    if stype in ('Affirmative', 'Staff'):
        AffirmativeStaffApplication.objects.filter(pk=pk).delete()
    else:
        Application.objects.filter(pk=pk).delete()
    return redirect(f'{back}&deleted=1')


@_vpsea_required
def vpsea_new_semester(request):
    from .models import (
        SystemSettings, ScholarListImport, ActivityLog, Application,
        AffirmativeStaffApplication, ImportedScholar,
    )
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

    outgoing_label = settings_obj.academic_year
    outgoing = SystemSettings.parse_label(outgoing_label)

    settings_obj.academic_year = label
    settings_obj.active_semester = parsed['semester']
    settings_obj.save()

    _base = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    ALL_TYPES = _base + [t for t in Scholarship.objects.values_list('type', flat=True).distinct() if t not in _base]

    def _build_excel(scholarship_type):
        col_map = COLUMN_MAPS.get(scholarship_type, COLUMN_MAPS['CoScho'])
        hint = COLUMN_HINTS.get(scholarship_type, COLUMN_HINTS['CoScho'])
        header = [h.strip() for h in hint.split('|')]

        if scholarship_type in ('Affirmative', 'Staff'):
            qs = AffirmativeStaffApplication.objects.filter(
                status='Approved', qualified_for=scholarship_type
            ).select_related(*STAFF_APPLICATION_DETAILS).order_by('full_name')
        else:
            qs = Application.objects.filter(
                status='Approved', scholarship__type=scholarship_type
            ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name')

        imported = list(ImportedScholar.objects.filter(
            scholarship_type=scholarship_type, term_label=outgoing_label,
            claimed_by__isnull=True,
        ).order_by('last_name', 'first_name'))

        records = list(qs) + imported
        programme_name = (
            Scholarship.objects.filter(type=scholarship_type)
            .values_list('name', flat=True).first() or scholarship_type
        )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Scholars'
        ws.append(header)
        for i, record in enumerate(records, 1):
            cells = _rollover_fields(record, programme_name)
            row = [''] * len(header)
            row[0] = i
            for idx, field in col_map:
                row[idx] = cells.get(field, '')
            ws.append(row)

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf, len(records)

    created = 0
    for t in ALL_TYPES:
        if ScholarListImport.objects.filter(term_label=outgoing_label, scholarship_type=t).exists():
            continue
        buf, count = _build_excel(t)
        rollover = ScholarListImport(
            scholarship_type=t,
            school_year=outgoing['sy'],
            semester=outgoing['semester'],
            term_label=outgoing_label,
            scholar_count=count,
            imported_by=request.user,
        )
        rollover.excel_file.save(f'{t}_{outgoing_label}.xlsx', ContentFile(buf.read()), save=True)
        created += 1

    ActivityLog.objects.create(
        user=request.user,
        action=f'New semester started: {label} ({parsed["sy"]} {parsed["semester"]}). '
               f'Saved lists for {created} scholarship types under {outgoing_label}.'
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


def _rollover_fields(record, programme_name=''):
    from .models import ImportedScholar

    if isinstance(record, ImportedScholar):
        return {
            'last_name': record.last_name,
            'first_name': record.first_name,
            'middle_name': record.middle_name,
            'middle_initial': (record.middle_name or '')[:1],
            'sex': record.gender or '',
            'barangay': record.barangay or '',
            'municipality': record.municipality or '',
            'province': record.province or '',
            'course': record.course or '',
            'year': record.year_level or '',
            'gwa': f'{record.gwa:.2f}' if record.gwa else '',
            'student_number': record.student_id or '',
            'award_number': record.award_number or '',
            'congress_district': record.congress_district or '',
            'pct': '', 'pct_type': '',
            'scholarship': programme_name,
            'scholarship_program': programme_name,
        }

    if isinstance(record, AffirmativeStaffApplication):
        pct = '100' if record.is_nsu_staff else '75'
        name = ('BiPSU Staff Scholarship' if record.is_nsu_staff
                else 'Affirmative Action Scholarship')
        return {
            'last_name': record.last_name,
            'first_name': record.first_name,
            'middle_name': record.middle_name,
            'middle_initial': record.middle_initial,
            'sex': record.gender or '',
            'barangay': record.barangay or '',
            'municipality': record.municipality or '',
            'province': record.province or '',
            'course': record.course or '',
            'year': record.year_level or '',
            'gwa': '',
            'student_number': record.student_id or '',
            'award_number': '',
            'congress_district': '',
            'pct': pct, 'pct_type': pct,
            'scholarship': name, 'scholarship_program': name,
        }

    profile = record.student
    gwa = profile.gwa or 0
    if record.scholarship.type == 'Academic':
        pct = 'Univ. Scholar' if gwa <= 1.29 else ('College Scholar' if gwa <= 1.50 else '')
    else:
        pct = ''
    return {
        'last_name': profile.user.last_name or '',
        'first_name': profile.user.first_name or '',
        'middle_name': profile.middle_name or '',
        'middle_initial': profile.middle_initial,
        'sex': profile.gender or '',
        'barangay': profile.barangay or '',
        'municipality': profile.municipality or '',
        'province': profile.province or '',
        'course': profile.course or '',
        'year': profile.year_level or '',
        'gwa': f'{gwa:.2f}' if gwa else '',
        'student_number': profile.student_id or '',
        'award_number': record.award_number or '',
        'congress_district': record.congress_district or '',
        'pct': pct, 'pct_type': pct,
        'scholarship': record.scholarship.name,
        'scholarship_program': record.scholarship.name,
    }


def _delete_import_with_scholars(record):
    from .models import ImportedScholar

    stype, label = record.scholarship_type, record.term_label
    with transaction.atomic():
        removed, _ = ImportedScholar.objects.filter(
            scholarship_type=stype, term_label=label,
        ).delete()
        record.excel_file.delete(save=False)
        record.delete()
    return removed, stype, label


@_vpsea_required
def vpsea_imported_delete(request, pk):
    from .models import ImportedScholar, ActivityLog
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('scholarship_type', 'Academic')
    row = ImportedScholar.objects.filter(pk=pk).first()
    if not row:
        return redirect(f'/vpsea/archives/?type={stype}')
    label = f'{row.full_name} ({row.scholarship_type} {row.term_label})'
    row.delete()
    ActivityLog.objects.create(
        user=request.user,
        action=f'Deleted imported scholar {label}.',
    )
    return redirect(f'/vpsea/archives/?type={stype}&deleted=1')


@_vpsea_required
def vpsea_rollover_delete(request, pk):
    from .models import ScholarListImport, ActivityLog
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('type', 'Academic')
    try:
        r = ScholarListImport.objects.get(pk=pk)
    except ScholarListImport.DoesNotExist:
        return redirect(f'/vpsea/archives/?type={stype}')
    removed, imported_type, label = _delete_import_with_scholars(r)
    ActivityLog.objects.create(
        user=request.user,
        action=f'Deleted the {imported_type} import for "{label}" and the '
               f'{removed} scholar row(s) it had created.'
    )
    return redirect(f'/vpsea/archives/?type={stype}')


def _custom_columns_for(stype, override=None):
    programme = Scholarship.objects.filter(type=stype).first()
    return [column for column
            in scholar_columns.resolve(programme, stype, override=override)
            if column['custom']]


def _sheet_custom_columns(headings, col_map, columns):
    by_key = {column['key']: column for column in columns}
    claimed = {0} | {index for index, _field in col_map}

    matched = {}
    for index, heading in enumerate(headings):
        if index in claimed or heading is None:
            continue
        column = by_key.get(scholar_columns.custom_key(str(heading)))
        if column is not None and column['key'] not in {c['key'] for c in matched.values()}:
            matched[index] = column
    return matched


def _cell_for_custom_column(column, raw):
    import datetime

    if isinstance(raw, datetime.datetime):
        raw = raw.date().isoformat()
    elif isinstance(raw, datetime.date):
        raw = raw.isoformat()
    if raw is None or str(raw).strip() == '':
        return ''
    return scholar_columns.clean_value(column, raw)


def _scholars_from_sheet(file, stype, term_label, imported_from=None,
                         custom_columns=None):
    import openpyxl

    from .models import ImportedScholar

    ws = openpyxl.load_workbook(file).active
    col_map = COLUMN_MAPS.get(stype, COLUMN_MAPS['CoScho'])

    if custom_columns is None:
        custom_columns = _custom_columns_for(stype)
    headings = [cell.value for cell in ws[1]] if ws.max_row else []
    from_sheet = _sheet_custom_columns(headings, col_map, custom_columns)

    records, refused = [], 0
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

        added = {}
        for index, column in from_sheet.items():
            cleaned = _cell_for_custom_column(
                column, row[index] if index < len(row) else None)
            if cleaned is None:
                refused += 1
            elif cleaned != '':
                added[column['key']] = cleaned

        records.append(ImportedScholar(
            scholarship_type=stype,
            term_label=term_label,
            last_name=last,
            first_name=first,
            middle_name=extra.get('middle_name', extra.get('middle_initial', '')),
            gender=extra.get('sex', ''),
            course=extra.get('course', ''),
            year_level=year_level,
            gwa=gwa,
            barangay=extra.get('barangay', addr_parts[0] if len(addr_parts) > 0 else ''),
            municipality=extra.get('municipality', addr_parts[1] if len(addr_parts) > 1 else ''),
            province=extra.get('province', addr_parts[2] if len(addr_parts) > 2 else ''),
            student_id=extra.get('student_number', extra.get('student_id', '')),
            award_number=extra.get('award_number', ''),
            congress_district=extra.get('congress_district', ''),
            extra_data=added,
            imported_from=imported_from or file.name,
        ))
    return records, refused


@_vpsea_required
def vpsea_archive_import(request):
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

        records, refused = _scholars_from_sheet(file, stype, rollover_label)

        with transaction.atomic():
            ImportedScholar.objects.filter(
                scholarship_type=stype, term_label=rollover_label).delete()
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
    except Exception as exc:
        from urllib.parse import quote
        return redirect(f'/vpsea/archives/?type={quote(stype)}&import_error='
                        + quote(str(exc)))
    target = f'/vpsea/archives/?type={stype}&import_ok={created}'
    if refused:
        target += f'&columns_bad={refused}'
    return redirect(target)



@_vpsea_required
def vpsea_archive_download(request):
    from urllib.parse import quote

    from .models import SystemSettings

    stype = request.GET.get('type', 'Academic')
    if stype == UNAWARDED_TAB:
        return redirect(f'/vpsea/archives/?type={quote(stype)}')

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    _labels, term = _archive_term(request, stype, settings_obj.academic_year)
    parsed = SystemSettings.parse_label(term)

    tier = request.GET.get('tier', '')
    if stype != 'CHED' or tier not in CHED_ARCHIVE_TIERS:
        tier = ''

    programme = Scholarship.objects.filter(type=stype).first()
    columns = scholar_columns.resolve(programme, stype, 'vpsea')
    groups = _archive_records(stype, term, tier)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _sheet_name(f'{stype} {tier} Merit Scholars' if tier
                           else f'{stype} Scholars')

    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    width = len(columns) + 1

    line = 1

    def banner(text, fill, font):
        nonlocal line
        ws.cell(row=line, column=1, value=text)
        ws.merge_cells(start_row=line, start_column=1, end_row=line, end_column=width)
        cell = ws.cell(row=line, column=1)
        cell.font, cell.fill, cell.alignment, cell.border = font, fill, center, border
        line += 1

    banner(f'{programme.name if programme else stype} — LIST OF SCHOLARS',
           PatternFill('solid', fgColor='1F4E79'),
           Font(bold=True, size=12, color='FFFFFF'))
    banner(f"{parsed['semester']} — SY {parsed['sy']}",
           PatternFill('solid', fgColor='BDD7EE'), Font(bold=True, size=10))
    line += 1

    header_fill = PatternFill('solid', fgColor='D9E1F2')
    for title, records, _empty in groups:
        if title:
            banner(title, PatternFill('solid', fgColor='BDD7EE'),
                   Font(bold=True, size=10))
        for index, label in enumerate(['No.'] + [c['label'] for c in columns], 1):
            cell = ws.cell(row=line, column=index, value=label)
            cell.font, cell.fill = Font(bold=True), header_fill
            cell.border, cell.alignment = border, center
        line += 1
        for row in scholar_columns.rows_for(records, columns):
            ws.cell(row=line, column=1, value=row['no']).border = border
            for index, (column, cell_value) in enumerate(zip(columns, row['cells']), 2):
                out = ws.cell(row=line, column=index,
                              value=scholar_columns.excel_value(column, cell_value['value']))
                out.border = border
                out.alignment = Alignment(vertical='center', wrap_text=True)
            line += 1
        line += 1

    from openpyxl.utils import get_column_letter

    for index, column_cells in enumerate(ws.columns, 1):
        longest = max((len(str(c.value)) for c in column_cells if c.value), default=0)
        ws.column_dimensions[get_column_letter(index)].width = min(longest + 4, 40)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    safe = ''.join(c if c.isalnum() else '_' for c in f'{stype}_scholars_{term}')
    response['Content-Disposition'] = f'attachment; filename="{safe}.xlsx"'
    return response


_BAD_SHEET_CHARS = str.maketrans({c: '-' for c in '[]:*?/' + chr(92)})


def _sheet_name(title):
    return (title.translate(_BAD_SHEET_CHARS).strip() or 'Scholars')[:31]


def _rollover_workbook(field_file):
    with field_file.open('rb') as handle:
        return openpyxl.load_workbook(BytesIO(handle.read()))


def _analytics_context(request, all_types, include_gwa=True):
    from .models import ScholarListImport, SystemSettings
    from collections import defaultdict

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    ALL_TYPES = list(all_types)

    from .models import ImportedScholar

    def _imported_current(stype):
        return ImportedScholar.objects.filter(
            scholarship_type=stype, term_label=active_label, claimed_by__isnull=True,
        )

    all_labels = list(
        ScholarListImport.objects.values_list('term_label', flat=True)
        .distinct().order_by('-term_label')
    )
    ar_labels = list(
        ImportedScholar.objects.exclude(term_label='')
        .values_list('term_label', flat=True).order_by().distinct()
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

    def _sheet_for(stype):
        return ScholarListImport.objects.filter(
            scholarship_type=stype, term_label=selected_label).first()

    rollover_counts = {}
    for t in ALL_TYPES:
        if selected_label == active_label:
            if t in ('Affirmative', 'Staff'):
                from .models import AffirmativeStaffApplication
                counted = AffirmativeStaffApplication.objects.filter(
                    status='Approved', qualified_for=t
                ).count()
            else:
                counted = Application.objects.filter(
                    status='Approved', scholarship__type=t
                ).count()
            counted += _imported_current(t).count()
        else:
            counted = ImportedScholar.objects.filter(
                scholarship_type=t, term_label=selected_label).count()

        if not counted:
            record = _sheet_for(t)
            counted = record.scholar_count if record else 0
        rollover_counts[t] = counted

    def _course_counts_from_sheet(stype):
        r = _sheet_for(stype)
        if not r or not r.excel_file:
            return {}
        try:
            ws = _rollover_workbook(r.excel_file).active
            course_col = next((cell.column - 1 for cell in ws[1] if cell.value and 'course' in str(cell.value).lower()), None)
            if course_col is None:
                return {}
            counts = defaultdict(int)
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[0] is not None and course_col < len(row) and row[course_col]:
                    counts[str(row[course_col]).strip()] += 1
            return dict(counts)
        except Exception:
            logger.exception('analytics: could not read rollover sheet for %s %s',
                             stype, selected_label)
            return {}

    def _course_counts_from_rollover(stype):
        counts = {}
        if selected_label == active_label:
            from django.db.models import Count as DCount
            if stype in ('Affirmative', 'Staff'):
                from .models import AffirmativeStaffApplication
                qs = AffirmativeStaffApplication.objects.filter(
                    status='Approved', qualified_for=stype
                ).values('enrollment__course').annotate(n=DCount('id'))
                for r in qs:
                    key = r['enrollment__course'] or 'Unknown'
                    counts[key] = counts.get(key, 0) + r['n']
            else:
                qs = Application.objects.filter(
                    status='Approved', scholarship__type=stype
                ).values('student__enrollment__course').annotate(n=DCount('id'))
                for r in qs:
                    key = r['student__enrollment__course'] or 'Unknown'
                    counts[key] = counts.get(key, 0) + r['n']
            for r in _imported_current(stype).values('course').annotate(n=DCount('id')):
                key = r['course'] or 'Unknown'
                counts[key] = counts.get(key, 0) + r['n']
        else:
            for rec in ImportedScholar.objects.filter(
                scholarship_type=stype, term_label=selected_label
            ).values('course'):
                c = rec['course'] or 'Unknown'
                counts[c] = counts.get(c, 0) + 1

        return counts or _course_counts_from_sheet(stype)

    if selected_type and selected_type in ALL_TYPES:
        raw = _course_counts_from_rollover(selected_type)
    else:
        raw = defaultdict(int)
        for t in ALL_TYPES:
            for k, v in _course_counts_from_rollover(t).items():
                raw[k] += v
    course_dist = [{'course': k, 'scholars': v} for k, v in sorted(raw.items(), key=lambda x: -x[1])]

    GWA_BANDS = ['1.00-1.25', '1.26-1.50', '1.51-1.75', '1.76-2.00', '2.01-2.50']

    def _band(value):
        try:
            g = float(value or 0)
        except (ValueError, TypeError):
            return None
        if g < 1.0:
            return None
        for band, ceiling in zip(GWA_BANDS, (1.25, 1.50, 1.75, 2.00, 2.50)):
            if g <= ceiling:
                return band
        return None

    def _banded(values):
        buckets = {band: 0 for band in GWA_BANDS}
        found = False
        for value in values:
            band = _band(value)
            if band:
                buckets[band] += 1
                found = True
        return buckets if found else None

    def _gwa_from_sheet():
        record = _sheet_for('Academic')
        if not record or not record.excel_file:
            return None
        try:
            ws = _rollover_workbook(record.excel_file).active
            gwa_col = next((cell.column - 1 for cell in ws[1]
                            if cell.value and 'gwa' in str(cell.value).lower()), None)
            if gwa_col is None:
                return None
            return _banded(
                row[gwa_col] for row in ws.iter_rows(min_row=2, values_only=True)
                if row and row[0] is not None and gwa_col < len(row)
            )
        except Exception:
            logger.exception('analytics: could not read Academic rollover '
                             'sheet for %s', selected_label)
            return None

    if not include_gwa:
        gpa_ranges = []
    else:
        if selected_label == active_label:
            buckets = _banded(
                [p['student__enrollment__gwa'] for p in Application.objects.filter(
                    status='Approved', scholarship__type='Academic'
                ).values('student__enrollment__gwa')]
                + [r['gwa'] for r in _imported_current('Academic').values('gwa')]
            )
        else:
            buckets = _banded(
                r['gwa'] for r in ImportedScholar.objects.filter(
                    scholarship_type='Academic', term_label=selected_label
                ).values('gwa')
            )
        buckets = buckets or _gwa_from_sheet() or {band: 0 for band in GWA_BANDS}
        gpa_ranges = [{'range': k, 'count': v} for k, v in buckets.items()]

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
                c += _imported_current(t).count()
            else:
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
            'sy': parsed['sy'],
            'display': parsed_display,
            'total': sum(counts.values()),
            'counts': counts,
            'per_type': {t: c for t, c in counts.items() if c},
        })

    if selected_type and selected_type in ALL_TYPES:
        series_types = [selected_type]
    else:
        series_types = [t for t in ALL_TYPES
                        if any(d['counts'].get(t) for d in trend_data)]
    trend_series = [
        {'type': t, 'counts': [d['counts'].get(t, 0) for d in trend_data]}
        for t in series_types
    ]

    def _identity(student_id, last, first):
        digits = ''.join(ch for ch in (student_id or '').upper() if ch.isalnum())
        if digits:
            return f'id:{digits}'
        name = ' '.join(' '.join((last or '', first or '')).upper().split())
        return f'name:{name}' if name else None

    def _identities_from_sheet(stype, label):
        record = ScholarListImport.objects.filter(
            scholarship_type=stype, term_label=label).first()
        if not record or not record.excel_file:
            return set()
        try:
            ws = _rollover_workbook(record.excel_file).active

            def column(*wanted):
                for cell in ws[1]:
                    heading = str(cell.value or '').strip().lower()
                    if heading and any(w in heading for w in wanted):
                        return cell.column - 1
                return None

            last_col = column('last name')
            first_col = column('first name')
            id_col = column('student number', 'student id', 'student no')
            if last_col is None and id_col is None:
                return set()

            def cell(row, index):
                if index is None or index >= len(row):
                    return ''
                return str(row[index]).strip() if row[index] is not None else ''

            people = set()
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or row[0] is None:
                    continue
                key = _identity(cell(row, id_col), cell(row, last_col),
                                cell(row, first_col))
                if key:
                    people.add(key)
            return people
        except Exception:
            logger.exception('analytics: could not read rollover sheet for %s %s',
                             stype, label)
            return set()

    def _scholars_in(stype, label):
        people = set()

        if label == active_label:
            if stype in ('Affirmative', 'Staff'):
                from .models import AffirmativeStaffApplication
                for r in AffirmativeStaffApplication.objects.filter(
                    status='Approved', qualified_for=stype
                ).values('enrollment__student_id', 'full_name'):
                    parts = (r['full_name'] or '').split()
                    people.add(_identity(r['enrollment__student_id'],
                                         parts[-1] if parts else '',
                                         parts[0] if len(parts) > 1 else ''))
            else:
                for r in Application.objects.filter(
                    status='Approved', scholarship__type=stype
                ).values('student__student_id', 'student__user__last_name',
                         'student__user__first_name'):
                    people.add(_identity(r['student__student_id'],
                                         r['student__user__last_name'],
                                         r['student__user__first_name']))
            rows = _imported_current(stype)
        else:
            rows = ImportedScholar.objects.filter(
                scholarship_type=stype, term_label=label)

        for r in rows.values('student_id', 'last_name', 'first_name'):
            people.add(_identity(r['student_id'], r['last_name'], r['first_name']))

        people.discard(None)
        return people or _identities_from_sheet(stype, label)

    year_people = {}
    for d in trend_data:
        people = year_people.setdefault(d['sy'], set())
        for t in series_types:
            people |= _scholars_in(t, d['label'])
    year_dist = [{'year': sy, 'scholars': len(people)}
                 for sy, people in sorted(year_people.items())]

    show_program = bool(course_dist) if selected_type else any(rollover_counts.values())
    show_gwa = (
        bool(gpa_ranges)
        and (not selected_type or selected_type == 'Academic')
        and any(g['count'] for g in gpa_ranges)
    )
    show_trend = len(trend_data) > 1 and any(any(s['counts']) for s in trend_series)
    show_years = any(y['scholars'] for y in year_dist)

    return {
        'rollover_counts': rollover_counts,
        'all_types': ALL_TYPES,
        'course_dist': course_dist,
        'gpa_ranges': gpa_ranges,
        'show_program': show_program,
        'show_gwa': show_gwa,
        'show_trend': show_trend,
        'show_years': show_years,
        'all_sy_display': all_sy_display,
        'selected_sy': selected_label,
        'selected_type': selected_type,
        'selected_sy_display': f"{selected_sy} — {selected_semester}",
        'active_sy': active_label,
        'trend_data': trend_data,
        'trend_series': trend_series,
        'year_dist': year_dist,
    }


@_vpsea_required
def vpsea_analytics(request):
    _base = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    all_types = _base + [
        t for t in Scholarship.objects.values_list('type', flat=True).distinct()
        if t not in _base
    ]
    return render(request, 'vpsea/analytics.html', _analytics_context(request, all_types))


@_vpsea_required
def vpsea_announcements(request):
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


def _report_term(request):
    from .models import SystemSettings
    from . import masterlist_report
    label = masterlist_report.term_for(request.GET.get('sy'))
    display = [(l, '{sy} — {semester}'.format(**SystemSettings.parse_label(l)))
               for l in masterlist_report.known_terms()]
    return label, SystemSettings.parse_label(label), display


@_vpsea_required
def vpsea_reports(request):
    import os
    from .models import SystemSettings
    from . import doc_convert, masterlist_report

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    label, parsed, all_sy_display = _report_term(request)
    context, summary = masterlist_report.build_context(term_label=label)

    sections = []
    for entry in summary:
        slot = context[entry['slot']]
        gendered = entry['layout'] == 'gendered'
        headers = entry['headers']

        def cells(rows):
            return [masterlist_report.cells_for(r, headers) for r in rows]

        sections.append((
            entry['heading'],
            headers,
            cells(slot['female'] if gendered else slot['students']),
            cells(slot['male']) if gendered else [],
            gendered,
            entry['key'].lower(),
        ))

    active = SystemSettings.parse_label(settings_obj.academic_year)
    return render(request, 'vpsea/reports.html', {
        'sections': sections,
        'semester': parsed['semester'],
        'ay': parsed['sy'],
        'all_sy_display': all_sy_display,
        'selected_sy': label,
        'is_active_term': label == settings_obj.academic_year,
        'active_sy_display': f"{active['sy']} — {active['semester']}",
        'grand_total': sum(e['total'] for e in summary),
        'summary': summary,
        'template_available': os.path.exists(masterlist_report.TEMPLATE_PATH),
        'exact_preview': doc_convert.available(),
        'error': request.GET.get('error'),
    })


@_vpsea_required
@xframe_options_exempt
def vpsea_report_preview_pdf(request):
    from . import doc_convert, masterlist_report, report_pdf

    term, parsed, _display = _report_term(request)
    label = term.replace('-', '_')

    pdf = None
    if doc_convert.available():
        try:
            buf, _summary = masterlist_report.build_document(
                parsed['sy'], parsed['semester'], term_label=term)
            pdf = doc_convert.to_pdf(buf.getvalue(), '.docx')
        except (FileNotFoundError, doc_convert.ConversionUnavailable,
                doc_convert.ConversionFailed):
            pdf = None
    if pdf is None:
        buf, _summary = report_pdf.masterlist_pdf(
            parsed['sy'], parsed['semester'], term_label=term)
        pdf = buf.read()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="BiPSU_List_of_Scholars_{label}.pdf"')
    return response


@_vpsea_required
def vpsea_report_download(request):
    from . import masterlist_report

    term, parsed, _display = _report_term(request)
    try:
        buf, _summary = masterlist_report.build_document(
            parsed['sy'], parsed['semester'], term_label=term)
    except FileNotFoundError as exc:
        from urllib.parse import quote
        return redirect(f'/vpsea/reports/?sy={quote(term)}&error={quote(str(exc))}')

    label = term.replace('-', '_')
    filename = f'BiPSU_List_of_Scholars_{label}.docx'
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
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
    from .models import Application, AffirmativeStaffApplication

    term, parsed, _display = _report_term(request)
    semester = parsed['semester']
    ay = parsed['sy']

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

    current_row = [1]

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

    MAX_COLS = 13

    write_title('Republic of the Philippines', MAX_COLS)
    write_title('BILIRAN PROVINCE STATE UNIVERSITY — Naval, Biliran', MAX_COLS)
    write_title(f'LIST OF SCHOLARS FOR {semester} SY: {ay}', MAX_COLS)
    blank_row()

    academic = list(Application.objects.filter(
        status='Approved', scholarship__type='Academic'
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
    females_a = [a for a in academic if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    female_pks_a = {a.pk for a in females_a}
    males_a   = [a for a in academic if a.pk not in female_pks_a]

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

    staff = list(AffirmativeStaffApplication.objects.filter(
        status='Approved', qualified_for='Staff'
    ).select_related(*STAFF_APPLICATION_DETAILS).order_by('full_name'))
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

    affirmative = list(AffirmativeStaffApplication.objects.filter(
        status='Approved', qualified_for='Affirmative'
    ).select_related(*STAFF_APPLICATION_DETAILS).order_by('full_name'))
    aff_females = [a for a in affirmative if a.gender and a.gender.upper() in ('F', 'FEMALE')]
    female_pks  = {a.pk for a in aff_females}
    aff_males   = [a for a in affirmative if a.pk not in female_pks]
    headers_aff = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    write_section(f'AFFIRMATIVE ACTION (*) SCHOLARSHIP GRANT — {semester} SY: {ay}',
                  len(headers_aff))

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

    ched_all = list(Application.objects.filter(
        status='Approved', scholarship__type='CHED'
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
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
        female_pks = {a.pk for a in bf}
        bm = [a for a in block_apps if a.pk not in female_pks]
        write_gender_label('FEMALE', len(headers_ched))
        write_headers(headers_ched)
        write_rows(ched_rows(bf))
        write_gender_label('MALE', len(headers_ched))
        write_headers(headers_ched)
        write_rows(ched_rows(bm))
        blank_row()

    dost_all = list(Application.objects.filter(
        status='Approved', scholarship__type='DOST'
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
    write_section(f'DOST (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
    dost_f = [a for a in dost_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    dost_female_pks = {a.pk for a in dost_f}
    dost_m = [a for a in dost_all if a.pk not in dost_female_pks]
    write_gender_label('FEMALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(dost_f))
    write_gender_label('MALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(dost_m))
    blank_row()

    gsis_all = list(Application.objects.filter(
        status='Approved', scholarship__type='GSIS'
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
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
    gsis_female_pks = {a.pk for a in gsis_f}
    gsis_m = [a for a in gsis_all if a.pk not in gsis_female_pks]
    write_gender_label('FEMALE', len(headers_gsis))
    write_headers(headers_gsis)
    write_rows(gsis_rows(gsis_f))
    write_gender_label('MALE', len(headers_gsis))
    write_headers(headers_gsis)
    write_rows(gsis_rows(gsis_m))
    blank_row()

    tes_all = list(Application.objects.filter(
        status='Approved', scholarship__type='TDP'
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
    write_section(f'TERTIARY EDUCATION SUBSIDY -TES (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
    tes_f = [a for a in tes_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    tes_female_pks = {a.pk for a in tes_f}
    tes_m = [a for a in tes_all if a.pk not in tes_female_pks]
    write_gender_label('FEMALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(tes_f))
    write_gender_label('MALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(tes_m))
    blank_row()
    blank_row()

    footer_text = (
        'Prepared by:\t\t\t\t\tNoted:\t\t\t\t\t\tRecommending approval:\t\t\t\t\t\tApproved:\n'
        'MARICEL S. SAULAN\t\t\t\tNORMA M. DUALLO, Ph.D.TM\t\t\tERWIN G. SALVATIERRA, Ph. D.\t\t\tVICTOR C. CAÑEZO, JR., Ed. D.\n'
        'Scholarship in charge\t\t\t\tSDSO Director\t\t\t\t\tVP for Extension Services, Student and External Affairs\t\tUniversity President'
    )
    ws.oddFooter.center.text = footer_text
    ws.oddFooter.center.size = 8
    ws.evenFooter.center.text = footer_text
    ws.evenFooter.center.size = 8

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

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f'Scholarship_Report_{term.replace("-","_")}_{semester.replace(" ","_")}.xlsx'
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def mail_status(settings_obj):
    from django.conf import settings as django_settings

    backend = getattr(django_settings, 'EMAIL_BACKEND', '')
    if backend.endswith('locmem.EmailBackend'):
        route, detail = 'Test', 'Messages are collected in memory by the test suite.'
    elif backend == 'api.email_backends.BrevoEmailBackend':
        route, detail = 'Brevo', 'Sent over HTTPS on port 443.'
    elif backend.endswith('smtp.EmailBackend'):
        host = getattr(django_settings, 'EMAIL_HOST', '')
        port = getattr(django_settings, 'EMAIL_PORT', '')
        route = 'SMTP'
        detail = (f'Sent to {host} on port {port}. Render blocks outbound SMTP '
                  f'on its free plan, so this delivers nothing there however '
                  f'carefully it is filled in.')
    else:
        route = 'Not configured'
        detail = ('Messages are written to the service log and delivered to '
                  'nobody. Set BREVO_API_KEY, or EMAIL_HOST where SMTP is '
                  'reachable.')

    return {
        'route': route,
        'route_detail': detail,
        'enabled': getattr(django_settings, 'EMAIL_ENABLED', False),
        'key_set': bool(getattr(django_settings, 'BREVO_API_KEY', '')),
        'sender': getattr(django_settings, 'DEFAULT_FROM_EMAIL', ''),
        'site_url': getattr(django_settings, 'SITE_URL', ''),
        'last_at': settings_obj.last_mail_attempt_at,
        'last_to': settings_obj.last_mail_to,
        'last_subject': settings_obj.last_mail_subject,
        'last_error': settings_obj.last_mail_error,
    }


def _decide_added_scholarship(request):
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


@_vpsea_required
def vpsea_accounts(request):
    from .models import ActivityLog, StaffProfile, StudentProfile

    if request.method == 'POST' and request.POST.get('action') == 'test_email':
        from urllib.parse import quote
        to = (request.POST.get('test_to') or request.user.email or '').strip()
        if not to:
            return redirect('/vpsea/accounts/?error=Give+an+address+to+send+the+test+to')
        ok = notify.send_email(
            to, '[BiPSU SRMS] Test message',
            'This is a test from the BiPSU Scholarship Records Management '
            'System.\n\nIf you are reading it in an inbox, mail works: '
            'applicants will be told what the office decided, and registrants '
            'can confirm their address.')
        return redirect(f'/vpsea/accounts/?tested={1 if ok else 0}&to={quote(to)}')

    if request.method == 'POST' and request.POST.get('declaration_id'):
        return _decide_added_scholarship(request)

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

        staff_declared = declared_staff_scholarship(account)
        if staff_declared and action == 'approve':
            _award, problem = approve_declared_staff_scholarship(
                staff_declared, request.user, remarks=message)
            if problem:
                from urllib.parse import quote
                return redirect(f'/vpsea/accounts/?error={quote(problem)}')
        elif staff_declared:
            reject_declared_staff_scholarship(staff_declared, request.user, message)

        for declared in declared_scholarships(getattr(account, 'profile', None)):
            if action != 'approve':
                reject_declared_scholarship(declared, request.user, message)
                continue
            archive = None
            archive_id = request.POST.get(f'archive_id_{declared.pk}', '').strip()
            if archive_id:
                from .models import ImportedScholar, SystemSettings
                settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
                archive = ImportedScholar.objects.filter(
                    id=archive_id, scholarship_type=declared.scholarship_type,
                    term_label=settings_obj.academic_year, claimed_by__isnull=True,
                ).first()
                if not archive:
                    return redirect('/vpsea/accounts/?error=That+archive+row+is+no+'
                                    'longer+available')
            _award, problem = approve_declared_scholarship(
                declared, request.user, archive=archive, remarks=message,
                tier=request.POST.get(f'award_tier_{declared.pk}', ''))
            if problem:
                from urllib.parse import quote
                return redirect(f'/vpsea/accounts/?error={quote(problem)}')

        status = 'approved' if action == 'approve' else 'rejected'
        account.decide_verification(status, message, request.user)

        _in_app, emailed = notify.account_decision(
            account, status, account.verification_note)
        ActivityLog.objects.create(
            user=request.user,
            action=(f'Account {status}: {account.get_full_name() or account.email} '
                    f'({account.get_role_display()}) — {account.verification_note}'),
        )
        return redirect(f'/vpsea/accounts/?{action}d=1&emailed={1 if emailed else 0}')

    pending = list(User.objects.filter(
        verification_status='pending', role__in=('student', 'nsu_staff'),
    ).order_by('date_joined'))
    decided = list(User.objects.filter(
        verification_status__in=('approved', 'rejected'),
        role__in=('student', 'nsu_staff'), verified_at__isnull=False,
    ).select_related('verified_by').order_by('-verified_at')[:25])

    students = {p.user_id: p for p in StudentProfile.with_details().filter(
        user__in=pending + decided)}
    staff = {p.user_id: p for p in StaffProfile.objects.filter(
        user__in=pending + decided)}
    for account in pending + decided:
        account.student_profile = students.get(account.id)
        account.employee_profile = staff.get(account.id)

    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    for account in pending:
        account.staff_declared = declared_staff_scholarship(account)
        account.declarations = declared_scholarships(account.student_profile)
        for req in account.declarations:
            req.archive_candidates = list(_archive_candidates(req, active_label))
            req.other_semester_rows = list(
                _archive_candidates(req).exclude(term_label=active_label)[:5])

    from collections import defaultdict
    from .models import StaffScholarshipDeclaration

    per_student = defaultdict(list)
    for req in (ScholarshipLinkRequest.objects
                .select_related('reviewed_by', 'matched_archive')
                .filter(student__user__in=decided, filed_in_portal=False)
                .order_by('submitted_at', 'pk')):
        per_student[req.student_id].append(req)
    per_employee = {}
    for decl in (StaffScholarshipDeclaration.objects
                 .select_related('reviewed_by')
                 .filter(staff_user__in=decided).order_by('submitted_at')):
        per_employee[decl.staff_user_id] = decl
    for account in decided:
        account.staff_declared = per_employee.get(account.id)
        account.declarations = per_student.get(
            getattr(account.student_profile, 'pk', None), [])

    from django.conf import settings as django_settings
    from .models import CHED_TIER_CHOICES

    settings_obj.refresh_from_db()
    added = list(pending_declarations())
    for req in added:
        req.archive_candidates = list(_archive_candidates(req, active_label))
        req.other_semester_rows = list(
            _archive_candidates(req).exclude(term_label=active_label)[:5])

    return render(request, 'vpsea/accounts.html', {
        'active': 'accounts',
        'pending': pending,
        'decided': decided,
        'added_scholarships': added,
        'scholarship_decision': request.GET.get('scholarship', ''),
        'mail': mail_status(settings_obj),
        'tested': request.GET.get('tested'),
        'tested_to': request.GET.get('to', ''),
        'ched_tiers': CHED_TIER_CHOICES,
        'active_label': active_label,
        'error': request.GET.get('error', ''),
        'approved': request.GET.get('approved'),
        'rejected': request.GET.get('rejected'),
        'emailed': request.GET.get('emailed'),
        'email_enabled': django_settings.EMAIL_ENABLED,
    })


@_vpsea_required
def vpsea_profile(request):
    user = request.user
    errors = []
    saved = password_changed = False

    if request.method == 'POST':
        wanted_password = bool(request.POST.get('new_password') or
                               request.POST.get('current_password'))
        errors = _change_own_password(request, user)
        if not errors:
            user.first_name = (request.POST.get('first_name') or user.first_name).strip()
            user.last_name = (request.POST.get('last_name') or user.last_name).strip()
            if request.FILES.get('photo'):
                user.photo = request.FILES['photo']
            user.save(update_fields=['first_name', 'last_name', 'photo'])
            saved = True
            password_changed = wanted_password

    return render(request, 'vpsea/profile.html', {
        'active': 'profile',
        'saved': saved,
        'password_changed': password_changed,
        'errors': errors,
    })


@_vpsea_required
def vpsea_students(request):
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
            from .models import AffirmativeStaffApplication
            aff_emails = AffirmativeStaffApplication.objects.filter(
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


STUDENT_RECORD_FIELDS = (
    'first_name', 'last_name', 'email', 'password', 'student_id',
    'middle_name', 'suffix', 'birth_place', 'civil_status',
    'date_of_birth', 'gender', 'contact_number',
    'barangay', 'municipality', 'province',
    'school', 'course', 'level', 'department', 'curriculum', 'year_level',
    'learner_ref_no', 'entry_period', 'entry_date', 'exam_score', 'gwa',
    'family_income',
)


def _enrollment_fields(p, profile=None):
    def current(name, default=''):
        return getattr(profile, name, default) if profile is not None else default

    def number(name):
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


def _save_column_values(request, base_url, portal='vpsea'):
    from urllib.parse import urlencode

    from .models import AffirmativeStaffApplication, Application, ImportedScholar

    stype = request.POST.get('type', '')
    query = {k: v for k, v in (('type', stype), ('tier', request.POST.get('tier', '')),
                               ('sy', request.POST.get('sy', ''))) if v}

    def back(**extra):
        return f'{base_url}?{urlencode({**query, **extra})}' if query or extra else base_url

    if request.method != 'POST':
        return redirect(back())

    programme = Scholarship.objects.filter(type=stype).first()
    custom = {c['key']: c for c in scholar_columns.resolve(programme, stype, portal)
              if c['custom']}

    models_by_kind = {
        'award': Application,
        'imported': ImportedScholar,
        'staff': AffirmativeStaffApplication,
    }
    edits, refused = {}, 0
    for field, value in request.POST.items():
        parts = field.split('__')
        if len(parts) != 4 or parts[0] != 'extra':
            continue
        _, kind, pk, key = parts
        if kind not in models_by_kind or not pk.isdigit():
            continue
        column = custom.get(key)
        if column is None:
            continue
        cleaned = scholar_columns.clean_value(column, value)
        if cleaned is None:
            refused += 1
            continue
        edits.setdefault((kind, int(pk)), {})[key] = cleaned

    saved = 0
    for (kind, pk), values in edits.items():
        record = models_by_kind[kind].objects.filter(pk=pk).first()
        if record is None:
            continue
        current = scholar_columns.extra_values(record)
        if all(current.get(key, '') == value for key, value in values.items()):
            continue
        scholar_columns.set_extra_values(record, values)
        saved += 1

    extra = {'columns_saved': saved}
    if refused:
        extra['columns_bad'] = refused
    return redirect(back(**extra))


@_vpsea_required
def vpsea_archive_columns(request):
    return _save_column_values(request, '/vpsea/archives/')


def _doc_list():
    return [
        ('doc_certificate_of_grades',   'Certificate Of Grades',   'Official COG from the Registrar for the previous semester.'),
        ('doc_certificate_of_enrollment', 'Certificate Of Enrollment', 'Official COE from the Registrar for the current semester.'),
        ('doc_prospectus',              'Prospectus',              'Program prospectus or subject checklist showing enrolled subjects.'),
        ('doc_id_photo',                'Id Photo',                'Recent 2×2 ID photo with white background.'),
        ('doc_application_form',        'Application Form',        'Signed and accomplished scholarship application form.'),
    ]


@_vpsea_required
def vpsea_student_delete(request, pk):
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
    scholarships = Scholarship.objects.all().order_by('type')
    return render(request, 'vpsea/scholarships.html', {
        'scholarships': scholarships,
        'added': request.GET.get('added'),
        'saved': request.GET.get('saved'),
    })


def _column_picker_context(posted=None, scholarship=None, stype='', portal=''):
    from . import scholar_columns

    if posted is not None:
        chosen = scholar_columns.clean_choice(posted.getlist('table_columns'))
        custom = _posted_custom_columns(posted)
    else:
        chosen = scholar_columns.clean_choice(
            getattr(scholarship, 'table_columns', None))
        custom = list(getattr(scholarship, 'extra_columns', None) or [])
    if not chosen:
        chosen = scholar_columns.default_for(
            stype or getattr(scholarship, 'type', ''), portal)

    order = {key: i for i, key in enumerate(chosen)}
    catalogue = sorted(
        ({'key': k, 'label': l} for k, l in scholar_columns.COLUMNS),
        key=lambda c: (order.get(c['key'], len(order)),
                       0 if c['key'] in order else 1),
    )
    for position, column in enumerate(catalogue):
        column['position'] = order.get(column['key'])
        column['chosen'] = column['key'] in order
    custom = [{**column,
               'options_text': ', '.join(column.get('options') or ())}
              for column in custom]
    return {
        'column_catalogue': catalogue,
        'chosen_columns': chosen,
        'custom_columns': custom,
        'custom_types': scholar_columns.CUSTOM_TYPES,
    }


def _column_name_errors(posted):
    return [
        f'"{label}" is already a column the archive fills — tick it in the '
        'list above instead of adding it.'
        for label in scholar_columns.catalogue_clashes(
            posted.getlist('extra_columns'))
    ]


def _posted_custom_columns(posted):
    return scholar_columns.clean_custom(
        posted.getlist('extra_columns'),
        posted.getlist('extra_types'),
        posted.getlist('extra_options'),
    )


def _posted_logo(posted):
    from .constants import available_logos

    chosen = (posted.get('logo') or '').strip()
    return chosen if chosen in available_logos() else ''


def _posted_window(p, errors, kind='applications'):
    from datetime import date as _date

    raw_opens = (p.get(f'{kind}_open_on') or '').strip()
    raw_days = (p.get(f'{kind}_open_days') or '').strip()

    opens = None
    if raw_opens:
        try:
            opens = _date.fromisoformat(raw_opens)
        except ValueError:
            errors.append('The opening date must be a real date, as YYYY-MM-DD.')

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
        s.logo = _posted_logo(p)
        s.table_columns = scholar_columns.clean_choice(p.getlist('table_columns'))
        s.extra_columns = _posted_custom_columns(p)
        if not s.name: errors.append('Name is required.')
        if not s.type: errors.append('Type is required.')
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
    from django.db.models import Q

    if request.method == 'POST':
        Scholarship.objects.filter(pk=pk).update(is_active=Q(is_active=False))
    return redirect('/vpsea/scholarships/')


RANKING_TABS = [
    ('Affirmative', 'Affirmative Action'),
    ('TES', 'TES Recommendation'),
    ('Staff', 'Faculty and Staff Scholars'),
]


def _staff_ranking_data():
    from . import staff_ranking
    from .models import AffirmativeStaffApplication

    applications = (AffirmativeStaffApplication.objects
                    .filter(qualified_for='Staff')
                    .select_related(*STAFF_APPLICATION_DETAILS))

    evaluations = staff_ranking.rank(applications)

    decided = [e for e in evaluations if e.status != staff_ranking.FOR_VERIFICATION]
    needs_info = [e for e in evaluations if e.status == staff_ranking.FOR_VERIFICATION]
    position = 0
    for evaluation in decided:
        if evaluation.qualified:
            position += 1
            evaluation.rank = position
        else:
            evaluation.rank = None
    for evaluation in needs_info:
        evaluation.rank = None

    return {
        'rows': decided,
        'needs_info': needs_info,
        'total': len(evaluations),
        'counts': {
            'qualified': sum(1 for e in evaluations if e.status == staff_ranking.QUALIFIED),
            'verification': len(needs_info),
            'not_qualified': sum(1 for e in evaluations
                                 if e.status == staff_ranking.NOT_QUALIFIED),
            'employees': sum(1 for e in evaluations if e.standing == staff_ranking.STAFF),
            'dependents': sum(1 for e in evaluations if e.standing == staff_ranking.DEPENDENT),
        },
    }


def _vpsea_staff_ranking(request):
    data = _staff_ranking_data()
    return render(request, 'vpsea/ranking.html', {
        'active': 'ranking',
        'ranking_tabs': RANKING_TABS,
        'active_tab': 'Staff',
        'staff_rows': data['rows'],
        'staff_needs_info': data['needs_info'],
        'staff_total': data['total'],
        'staff_counts': data['counts'],
    })


@_vpsea_required
def vpsea_ranking_download(request):
    from . import ranking_report
    from .models import ActivityLog

    tab = request.GET.get('type', 'Affirmative')
    if tab not in dict(RANKING_TABS):
        tab = 'Affirmative'

    threshold = None
    if tab == 'TES':
        data = _tes_ranking_data()
    elif tab == 'Staff':
        data = _staff_ranking_data()
    else:
        try:
            threshold = float(request.GET.get('passing', 75.0))
        except (TypeError, ValueError):
            threshold = 75.0
        data = _affirmative_ranking_data(threshold)

    buf, filename = ranking_report.build(tab, data, passing_threshold=threshold)

    ActivityLog.objects.create(
        user=request.user,
        action=f'Downloaded the {dict(RANKING_TABS)[tab]} recommendation list')

    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _affirmative_ranking_data(passing_threshold):
    from .affirmative_ranking import target_groups
    from .models import AffirmativeRecommendation

    recommendations = (
        AffirmativeRecommendation.objects
        .select_related('student__user', *STUDENT_DETAILS)
        .order_by('-fit_score', 'student__user__last_name')
    )

    rows = []
    for rec in recommendations:
        p = rec.student
        gpa_pass   = p.shs_gpa is not None and p.shs_gpa >= passing_threshold
        exam_pass  = p.suc_exam_percent is not None and p.suc_exam_percent >= 50.0
        not_tes    = not p.is_tes_beneficiary
        rows.append({
            'rank': None,
            'rec': rec,
            'profile': p,
            'gpa_pass': gpa_pass,
            'exam_pass': exam_pass,
            'not_tes': not_tes,
            'groups': target_groups(p),
            'eligible': gpa_pass and exam_pass and not_tes,
        })

    rows.sort(key=lambda r: (
        0 if r['eligible'] else 1,
        -r['groups'].count,
        -r['rec'].fit_score,
        (r['profile'].user.last_name or '').lower(),
    ))
    rank_counter = 1
    for row in rows:
        if row['eligible']:
            row['rank'] = rank_counter
            rank_counter += 1

    return {
        'rows': rows,
        'eligible_count': sum(1 for r in rows if r['eligible']),
        'ineligible_count': sum(1 for r in rows if not r['eligible']),
        'in_target_group_count': sum(1 for r in rows
                                     if r['eligible'] and r['groups'].count),
    }


def _tes_ranking_data():
    from . import tes_ranking

    profiles = StudentProfile.objects.filter(
        user__verification_status='approved',
    ).select_related('user', *StudentProfile.DETAIL_RELATIONS)

    complete, incomplete = tes_ranking.screen(profiles)
    evaluations = tes_ranking.rank(complete)

    position = 0
    for evaluation in evaluations:
        if evaluation.eligible:
            position += 1
            evaluation.rank = position
        else:
            evaluation.rank = None

    return {
        'rows': evaluations,
        'total': len(evaluations),
        'excluded': len(incomplete),
        'counts': {
            'eligible': sum(1 for e in evaluations if e.status == tes_ranking.ELIGIBLE),
            'excluded': len(incomplete),
            'not_eligible': sum(1 for e in evaluations if e.status == tes_ranking.NOT_ELIGIBLE),
            'priority_1': sum(1 for e in evaluations if e.priority == tes_ranking.PRIORITY_1),
            'priority_2': sum(1 for e in evaluations if e.priority == tes_ranking.PRIORITY_2),
        },
    }


def _vpsea_tes_ranking(request):
    data = _tes_ranking_data()
    return render(request, 'vpsea/ranking.html', {
        'active': 'ranking',
        'ranking_tabs': RANKING_TABS,
        'active_tab': 'TES',
        'tes_rows': data['rows'],
        'tes_excluded': data['excluded'],
        'tes_student_total': data['total'],
        'tes_counts': data['counts'],
    })


@_vpsea_required
def vpsea_ranking(request):
    from .models import AffirmativeRecommendation

    scholarship_type = request.GET.get('type', 'Affirmative')
    if scholarship_type == 'TES':
        return _vpsea_tes_ranking(request)
    if scholarship_type == 'Staff':
        return _vpsea_staff_ranking(request)
    scholarship_type = 'Affirmative'

    try:
        passing_threshold = float(request.GET.get('passing', 75.0))
    except (TypeError, ValueError):
        passing_threshold = 75.0

    if request.method == 'POST':
        if request.POST.get('action') == 'resync':
            AffirmativeRecommendation.evaluate_and_sync(passing_threshold)
        return redirect(f'/vpsea/ranking/?type={scholarship_type}&passing={passing_threshold}')

    AffirmativeRecommendation.evaluate_and_sync(passing_threshold)

    data = _affirmative_ranking_data(passing_threshold)
    return render(request, 'vpsea/ranking.html', {
        'ranking_tabs': RANKING_TABS,
        'active_tab': 'Affirmative',
        'rec_rows': data['rows'],
        'passing_threshold': passing_threshold,
        'eligible_count': data['eligible_count'],
        'ineligible_count': data['ineligible_count'],
        'in_target_group_count': data['in_target_group_count'],
    })


def _nsu_staff_required(view_fn):
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'nsu_staff':
            return redirect('/login/')
        return view_fn(request, *args, **kwargs)
    return wrapper


def _staff_profile(user):
    from .models import StaffProfile
    profile, _ = StaffProfile.objects.get_or_create(user=user)
    return profile


def _parse_date(raw):
    from datetime import datetime
    raw = (raw or '').strip()
    if not raw:
        return None, True
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date(), True
    except ValueError:
        return None, False


def _pick(application, staff, field):
    value = getattr(application, field, '') if application else ''
    return value or getattr(staff, field, '') or ''


def _pick_date(application, staff, field):
    value = getattr(application, field, None) if application else None
    value = value or getattr(staff, field, None)
    return value.strftime('%Y-%m-%d') if value else ''


def _nsu_staff_enrolled(user):
    from .models import AffirmativeStaffApplication
    return AffirmativeStaffApplication.objects.filter(
        email=user.email,
    ).exclude(status='Rejected').exists()


@_nsu_staff_required
def nsu_staff_dashboard(request):
    from .models import StaffRenewal, Notification, Announcement, AffirmativeStaffApplication
    user = request.user
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
    from .models import AffirmativeStaffApplication, StaffProfile
    from .constants import (BIPSU_STAFF_UNIT_GROUPS, CIVIL_STATUSES,
                            DESIGNATIONS, EMPLOYMENT_STATUSES)
    user = request.user
    staff = _staff_profile(user)
    aff_app = AffirmativeStaffApplication.objects.filter(
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
    from .models import AffirmativeStaffApplication, StaffRenewal
    user = request.user
    applications = AffirmativeStaffApplication.objects.filter(
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
    from .models import StaffRenewal, SystemSettings
    user = request.user
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    renewals = StaffRenewal.objects.filter(staff_user=user).order_by('-submitted_at')

    if request.method == 'POST':
        StaffRenewal.objects.create(
            staff_user=user,
            supporting_document=request.FILES.get('supporting_document') or None,
        )
        return redirect('/nsu-staff/renewal/?submitted=1')

    return render(request, 'nsu_staff/renewal.html', {
        'renewals': renewals,
        'submitted': request.GET.get('submitted'),
        'semester': parsed['semester'],
        'academic_year': parsed['sy'],
        'errors': [],
        'enrolled': _nsu_staff_enrolled(user),
    })


@_nsu_staff_required
def nsu_staff_apply(request):
    from .models import AffirmativeStaffApplication
    user = request.user
    staff = _staff_profile(user)

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
                existing = AffirmativeStaffApplication.objects.create(
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


@_vpsea_required
def vpsea_partners(request):
    from urllib.parse import quote

    from .constants import available_logos
    from .models import ActivityLog, PartnerOffice

    if request.method == 'POST':
        action = request.POST.get('action')
        back = '/vpsea/partners/'

        if action == 'create':
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
                return redirect(f'{back}?error={quote(" ".join(errors))}')

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
            ActivityLog.objects.create(
                user=request.user, action=f'Created the partner office {name}')
            return redirect(f'{back}?created={quote(name)}')

        office = PartnerOffice.objects.filter(pk=request.POST.get('office_id')).first()
        if not office:
            return redirect(f'{back}?error={quote("That partner was not found.")}')

        if action == 'access':
            was = office.name
            posted_name = request.POST.get('name')
            name = office.name if posted_name is None else posted_name.strip()
            if not name:
                return redirect(f'{back}?error={quote("A partner name is required.")}')
            if PartnerOffice.objects.filter(name__iexact=name).exclude(pk=office.pk).exists():
                return redirect(f'{back}?error={quote(f"A partner called {name} already exists.")}')

            office.name = name
            office.scholarships.set(_posted_partner_scholarships(request.POST))
            office.may_add_scholarships = bool(request.POST.get('may_add_scholarships'))
            office.logo = _posted_logo(request.POST)
            office.save(update_fields=['name', 'may_add_scholarships', 'logo'])
            renamed = f' and renamed it from {was}' if was != name else ''
            ActivityLog.objects.create(
                user=request.user,
                action=f'Changed what {office.name} can see{renamed}')
            return redirect(f'{back}?saved={quote(office.name)}')

        if action == 'password':
            account = office.accounts.filter(pk=request.POST.get('account_id')).first()
            password = request.POST.get('password') or ''
            if not account:
                return redirect(f'{back}?error={quote("That account is not this partner's.")}')
            if len(password) < 8:
                return redirect(f'{back}?error={quote("The password must be at least 8 characters.")}')
            account.set_password(password)
            account.save(update_fields=['password'])
            ActivityLog.objects.create(
                user=request.user,
                action=f'Reset the password for {account.email} ({office.name})')
            return redirect(f'{back}?saved={quote(office.name)}')

        if action == 'delete':
            name = office.name
            emails = list(office.accounts.values_list('email', flat=True))
            with transaction.atomic():
                office.accounts.all().delete()
                office.delete()
            ActivityLog.objects.create(
                user=request.user,
                action=f'Deleted the partner office {name} and {len(emails)} account(s)')
            return redirect(f'{back}?deleted={quote(name)}')

        if action == 'toggle':
            office.is_active = not office.is_active
            office.save(update_fields=['is_active'])
            state = 'Re-enabled' if office.is_active else 'Suspended'
            ActivityLog.objects.create(
                user=request.user, action=f'{state} the partner office {office.name}')
            return redirect(f'{back}?saved={quote(office.name)}')

        return redirect(f'{back}?error={quote("Unknown action.")}')

    offices = (PartnerOffice.objects
               .prefetch_related('scholarships', 'accounts')
               .order_by('name'))
    return render(request, 'vpsea/partners.html', {
        'offices': offices,
        'scholarships': Scholarship.objects.order_by('name'),
        'logos': available_logos(),
        'created': request.GET.get('created'),
        'saved': request.GET.get('saved'),
        'deleted': request.GET.get('deleted'),
        'error': request.GET.get('error'),
    })


def _partner_override(office, stype):
    from .models import PartnerTableColumns

    return (PartnerTableColumns.objects
            .filter(office=office, scholarship__type=stype)
            .select_related('scholarship').first())


def _posted_partner_scholarships(posted):
    return list(Scholarship.objects.filter(id__in=posted.getlist('scholarships')))


@_partner_required
def partner_dashboard(request, office):
    from .models import Application, ImportedScholar, SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)

    programmes = []
    for scholarship in office.scholarships.order_by('name'):
        approved = Application.objects.filter(
            status='Approved', scholarship__type=scholarship.type).count()
        imported = ImportedScholar.objects.filter(
            scholarship_type=scholarship.type, claimed_by__isnull=True).count()
        programmes.append({'scholarship': scholarship, 'total': approved + imported})

    return render(request, 'partner/dashboard.html', {
        'office': office,
        'programmes': programmes,
        'total': sum(p['total'] for p in programmes),
        'has_access': bool(programmes),
        'term': settings_obj.academic_year,
    })


@_partner_required
def partner_profile(request, office):
    user = request.user
    errors = []
    saved = password_changed = False

    if request.method == 'POST':
        wanted_password = bool(request.POST.get('new_password') or
                               request.POST.get('current_password'))
        errors = _change_own_password(request, user)
        if not errors:
            user.first_name = (request.POST.get('first_name') or user.first_name).strip()
            user.last_name = (request.POST.get('last_name') or user.last_name).strip()
            if request.FILES.get('photo'):
                user.photo = request.FILES['photo']
            user.save(update_fields=['first_name', 'last_name', 'photo'])
            saved = True
            password_changed = wanted_password

    return render(request, 'partner/profile.html', {
        'office': office,
        'programmes': office.scholarships.order_by('name'),
        'saved': saved,
        'password_changed': password_changed,
        'errors': errors,
    })


@_partner_required
def partner_archives(request, office):
    from .models import Application, ImportedScholar, ScholarListImport, SystemSettings

    types = office.visible_types()
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)

    stype = request.GET.get('type', '')
    if stype not in types:
        stype = types[0] if types else ''

    labels = []
    if stype:
        labels = sorted(
            set(ScholarListImport.objects.filter(scholarship_type=stype)
                .values_list('term_label', flat=True))
            | {settings_obj.academic_year},
            reverse=True,
        )
    selected = request.GET.get('sy', settings_obj.academic_year)
    if selected not in labels:
        selected = settings_obj.academic_year

    def _display(label):
        p = SystemSettings.parse_label(label)
        return f"{p['sy']} — {p['semester']}"

    active_label = settings_obj.academic_year
    history = []
    if stype:
        history = [
            {'label': lbl, 'display': _display(lbl), 'count': count}
            for lbl, count in (
                ScholarListImport.objects
                .filter(scholarship_type=stype).exclude(term_label=active_label)
                .order_by('-term_label')
                .values_list('term_label', 'scholar_count'))
        ]

    scholars, imported = [], []
    if stype:
        scholars = list(
            Application.objects
            .filter(status='Approved', scholarship__type=stype, term_label=selected)
            .select_related('student__user', 'scholarship', *STUDENT_DETAILS)
            .order_by('student__user__last_name', 'student__user__first_name'))
        imported = list(
            ImportedScholar.objects
            .filter(scholarship_type=stype, term_label=selected, claimed_by__isnull=True)
            .order_by('last_name', 'first_name'))

    override = _partner_override(office, stype) if stype else None
    groups = _scholar_groups(stype, [
        (None, scholars + imported,
         f'No {stype} scholars recorded for {selected}.'),
    ], portal='partner', override=override) if stype else {
        'columns': [], 'scholar_groups': [], 'has_custom_columns': False}

    programme = Scholarship.objects.filter(type=stype).first() if stype else None
    return render(request, 'partner/archives.html', dict(groups, **{
        'office': office,
        'archive_types': types,
        'active_type': stype,
        'all_sy': labels,
        'selected_sy': selected,
        'active_sy': active_label,
        'active_sy_display': _display(active_label),
        'selected_sy_display': _display(selected) if selected else '',
        'history': history,
        'col_hint': COLUMN_HINTS.get(stype, COLUMN_HINTS['CoScho']),
        'import_ok': request.GET.get('import_ok'),
        'import_error': request.GET.get('import_error'),
        'total': len(scholars) + len(imported),
        'uses_own_columns': override is not None,
        **(_column_picker_context(
            scholarship=override or programme, stype=stype, portal='partner')
           if stype else {}),
    }))


PARTNER_SCHOLAR_FIELDS = (
    'last_name', 'first_name', 'middle_name', 'gender', 'course',
    'student_id', 'award_number', 'congress_district',
    'barangay', 'municipality', 'province',
)


def _partner_scholar_values(posted):
    values = {name: (posted.get(name) or '').strip()
              for name in PARTNER_SCHOLAR_FIELDS}
    errors = []

    if not values['last_name'] and not values['first_name']:
        errors.append('A scholar needs at least a first or a last name.')

    raw_year = (posted.get('year_level') or '').strip()
    values['year_level'] = 0
    if raw_year:
        if raw_year.isdigit() and 1 <= int(raw_year) <= 10:
            values['year_level'] = int(raw_year)
        else:
            errors.append('Year level must be a whole number between 1 and 10.')

    raw_gwa = (posted.get('gwa') or '').strip()
    values['gwa'] = 0.0
    if raw_gwa:
        try:
            values['gwa'] = float(raw_gwa)
        except ValueError:
            errors.append('GWA must be a number, like 1.25.')

    return values, errors


@_partner_required
def partner_scholars(request, office):
    from urllib.parse import quote

    from .models import ActivityLog, ImportedScholar, SystemSettings

    back = '/partner/archives/'
    if request.method != 'POST':
        return redirect(back)

    p = request.POST
    stype = p.get('type', '')
    term = (p.get('sy') or '').strip()
    here = f'{back}?type={quote(stype)}' + (f'&sy={quote(term)}' if term else '')

    if stype not in office.visible_types():
        return redirect(f'{back}?error=' + quote(
            'That programme is not one this account can read.'))
    if not term:
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        term = settings_obj.academic_year
        here = f'{back}?type={quote(stype)}&sy={quote(term)}'

    action = p.get('action')

    scholar = None
    if action in ('edit', 'delete'):
        scholar = ImportedScholar.objects.filter(
            pk=p.get('scholar_id'), scholarship_type=stype,
            claimed_by__isnull=True,
        ).first()
        if not scholar:
            return redirect(f'{here}&error=' + quote(
                f'That scholar is not one this account can change. Your own '
                f'{stype} rows are; a scholar the office has matched to a BiPSU '
                'student account is theirs to correct.'))

    if action == 'delete':
        name = scholar.full_name or scholar.student_id or f'row #{scholar.pk}'
        scholar.delete()
        ActivityLog.objects.create(
            user=request.user,
            action=f'{office.name} deleted the {stype} scholar {name} ({term})')
        return redirect(f'{here}&scholar=deleted')

    if action not in ('add', 'edit'):
        return redirect(f'{here}&error=' + quote('Unknown action.'))

    values, errors = _partner_scholar_values(p)
    if errors:
        return redirect(f'{here}&error=' + quote(' '.join(errors)))

    if action == 'edit':
        for field, value in values.items():
            setattr(scholar, field, value)
        scholar.save()
        ActivityLog.objects.create(
            user=request.user,
            action=f'{office.name} edited the {stype} scholar '
                   f'{scholar.full_name} ({term})')
        return redirect(f'{here}&scholar=saved')

    scholar = ImportedScholar.objects.create(
        scholarship_type=stype, term_label=term,
        imported_from=f'Added by {office.name}',
        **values,
    )
    ActivityLog.objects.create(
        user=request.user,
        action=f'{office.name} added the {stype} scholar '
               f'{scholar.full_name} ({term})')
    return redirect(f'{here}&scholar=added')


@_partner_required
def partner_archive_import(request, office):
    from urllib.parse import quote

    from .models import ActivityLog, ImportedScholar, ScholarListImport, SystemSettings

    back = '/partner/archives/'
    if request.method != 'POST':
        return redirect(back)

    stype = request.POST.get('type', '')
    if stype not in office.visible_types():
        return redirect(f'{back}?error=' + quote(
            'That programme is not one this account can read.'))

    here = f'{back}?type={quote(stype)}'
    term = (request.POST.get('rollover_label') or '').strip()
    file = request.FILES.get('file')
    if not file:
        return redirect(f'{here}&import_error=' + quote('No file provided.'))
    if not term:
        return redirect(f'{here}&import_error=' + quote('A term label is required.'))

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    term_parsed = (SystemSettings.parse_label(term) if '-' in term
                   else {'sy': term, 'semester': parsed['semester']})

    try:
        records, refused = _scholars_from_sheet(
            file, stype, term, imported_from=f'{file.name} ({office.name})',
            custom_columns=_custom_columns_for(
                stype, override=_partner_override(office, stype)))
    except Exception as exc:
        return redirect(f'{here}&sy={quote(term)}&import_error=' + quote(
            f'That file could not be read as a {stype} list ({exc}).'))

    with transaction.atomic():
        replaced = ImportedScholar.objects.filter(
            scholarship_type=stype, term_label=term, claimed_by__isnull=True,
        ).delete()[0]
        ImportedScholar.objects.bulk_create(records)

        saved = ScholarListImport.objects.filter(
            scholarship_type=stype, term_label=term).first()
        if saved:
            saved.scholar_count = len(records)
            saved.save(update_fields=['scholar_count'])
        else:
            ScholarListImport.objects.create(
                scholarship_type=stype,
                school_year=term_parsed['sy'],
                semester=term_parsed.get('semester', parsed['semester']),
                term_label=term,
                scholar_count=len(records),
                imported_by=request.user,
            )

    ActivityLog.objects.create(
        user=request.user,
        action=f'{office.name} imported {file.name} ({len(records)} rows) for '
               f'{stype} as "{term}", replacing {replaced} of its own row(s)')
    target = f'{here}&sy={quote(term)}&import_ok={len(records)}'
    if refused:
        target += f'&columns_bad={refused}'
    return redirect(target)


@_partner_required
def partner_columns(request, office):
    from urllib.parse import quote

    from . import scholar_columns
    from .models import PartnerTableColumns

    back = '/partner/archives/'
    stype = (request.POST.get('type') if request.method == 'POST'
             else request.GET.get('type', '')) or ''
    if stype not in office.visible_types():
        return redirect(f'{back}?error=' + quote(
            'That programme is not one this account can read.'))

    programme = Scholarship.objects.filter(type=stype).first()
    if request.method != 'POST' or not programme:
        return redirect(f'{back}?type={quote(stype)}')

    chosen = scholar_columns.clean_choice(request.POST.getlist('table_columns'))
    if request.POST.get('action') == 'reset' or not chosen:
        PartnerTableColumns.objects.filter(office=office, scholarship=programme).delete()
        return redirect(f'{back}?type={quote(stype)}&columns=reset')

    PartnerTableColumns.objects.update_or_create(
        office=office, scholarship=programme,
        defaults={
            'table_columns': chosen,
            'extra_columns': _posted_custom_columns(request.POST),
        },
    )
    return redirect(f'{back}?type={quote(stype)}&columns=saved')


@_partner_required
def partner_report_download(request, office):
    from urllib.parse import quote

    from .models import SystemSettings

    stype = request.GET.get('type', '')
    if stype not in office.visible_types():
        return redirect('/partner/archives/?error=' + quote(
            'That programme is not one this account can read.'))

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    term = request.GET.get('sy', settings_obj.academic_year)
    buf, filename = _partner_workbook(office, stype, term)
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _partner_workbook(office, stype, term):
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    from . import scholar_columns
    from .models import Application, ImportedScholar

    programme = Scholarship.objects.filter(type=stype).first()
    columns = scholar_columns.resolve(
        programme, stype, 'partner', override=_partner_override(office, stype))

    records = list(
        Application.objects
        .filter(status='Approved', scholarship__type=stype, term_label=term)
        .select_related('student__user', 'scholarship', *STUDENT_DETAILS)
        .order_by('student__user__last_name', 'student__user__first_name')
    ) + list(
        ImportedScholar.objects
        .filter(scholarship_type=stype, term_label=term, claimed_by__isnull=True)
        .order_by('last_name', 'first_name')
    )

    wb = Workbook()
    ws = wb.active
    ws.title = (stype or 'Scholars')[:31]
    ws['A1'] = f'{office.name} — {stype} scholars'
    ws['A1'].font = Font(name='Arial', size=12, bold=True)
    ws['A2'] = f'Term {term}'
    ws['A2'].font = Font(name='Arial', size=10)

    head = 4
    for col, column in enumerate(columns, start=1):
        cell = ws.cell(row=head, column=col, value=column['label'])
        cell.font = Font(name='Arial', size=10, bold=True)
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        ws.column_dimensions[cell.column_letter].width = max(12, len(column['label']) + 4)

    for line, row in enumerate(scholar_columns.rows_for(records, columns), start=head + 1):
        for col, (column, cell_value) in enumerate(zip(columns, row['cells']), start=1):
            out = ws.cell(row=line, column=col,
                          value=scholar_columns.excel_value(column, cell_value['value']))
            out.font = Font(name='Arial', size=10)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    safe = ''.join(c if c.isalnum() else '_' for c in f'{office.name}_{stype}_{term}')
    return buf, f'{safe}.xlsx'

