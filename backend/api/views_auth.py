"""The public face: landing page, sign-in, registration, email confirmation.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from . import ratelimit
from .models import StudentProfile, Scholarship, User, ScholarshipLinkRequest, BIPSU_SCHOOLS, BIPSU_COURSES
from . import notify
import logging
from .views_shared import DECLARATION_SLOTS, _declaration_slots, _declared_scholarships, _disability_answer, _disability_fields, _positive_int, _tristate, _unanswered, _validate_proof, declarable_types

logger = logging.getLogger(__name__)


def _utm_payload(request):
    """Campaign parameters posted with a registration, if any.

    Bounded and parsed defensively — it arrives from a hidden form field,
    so it is caller-supplied data, not something to trust.
    """
    import json
    raw = (request.POST.get('utm_payload') or '').strip()
    if not raw or len(raw) > 2000:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}

def _active_catalogue():
    """The active scholarships for the landing page, cached.

    Keyed by the number of programmes and the latest update stamp, so
    editing a programme invalidates the entry without anything having to
    remember to clear it.
    """
    from django.conf import settings as django_settings
    from django.core.cache import cache
    from django.db.models import Count, Max

    stamp = Scholarship.objects.filter(is_active=True).aggregate(
        last=Max('updated_at'), total=Count('id'))
    marker = stamp['last'].timestamp() if stamp['last'] else 0
    key = f"landing:catalogue:{stamp['total']}:{marker}"

    rows = cache.get(key)
    if rows is None:
        rows = list(Scholarship.objects.filter(is_active=True).order_by('type'))
        cache.set(key, rows, django_settings.CATALOGUE_CACHE_SECONDS)
    return rows, stamp['last']

def landing_view(request):
    """The public landing page and scholarship catalogue."""
    if request.user.is_authenticated:
        portal = _portal_for(request.user)
        if portal != '/':
            return redirect(portal)
    rows, catalogue_updated = _active_catalogue()
    context = {
        'scholarships': rows,
        'internal': [s for s in rows if s.group == 'internal'],
        'external': [s for s in rows if s.group == 'external'],
        'institutional': [s for s in rows if s.group == 'institutional'],
        'catalogue_updated': catalogue_updated,
    }
    return render(request, 'landing.html', context)

PORTAL_FOR_ROLE = {
    'student': '/student/applications/',
    'nsu_staff': '/nsu-staff/',
    'vpsea': '/vpsea/',
    'partner': '/partner/',
    'super': '/super/',
}

def _portal_for(user):
    """The landing path for an account, by role."""
    return PORTAL_FOR_ROLE.get(user.role, '/')

def login_view(request):
    """Sign a caller in, throttling and refusing without naming who exists."""
    if request.user.is_authenticated:
        return redirect(_portal_for(request.user))

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password') or ''

        wait = ratelimit.retry_after(ratelimit.LOGIN, request, email)
        if wait is not None:
            return render(request, 'login.html', {
                'email': email,
                'error': ratelimit.wait_message(wait, 'sign-in attempts'),
            }, status=429)

        user = authenticate(request, username=email, password=password)
        if user and not user.can_sign_in:
            ratelimit.clear(ratelimit.LOGIN, request, email)
            return render(request, 'login.html', {
                'verification_status': user.verification_status,
                'verification_note': user.verification_note,
            })
        if user:
            ratelimit.clear(ratelimit.LOGIN, request, email)
            login(request, user)
            return redirect(_portal_for(user))

        if email and password:
            ratelimit.register_failure(ratelimit.LOGIN, request, email)
        return render(request, 'login.html', _sign_in_error(email, password),
                      status=401)
    return render(request, 'login.html')

SIGN_IN_REFUSED = (
    'Invalid email or password. Check both and try again — passwords are '
    'case-sensitive.'
)

def _sign_in_error(email, password):
    """Context for a refused sign-in that does not reveal who holds an account.

    Anyone who does not supply a working password gets one of two answers: a
    prompt to fill in a field they left blank, or a single message that reads
    the same whether the address is unknown, the password is wrong, or the
    account is closed. Distinguishing those would turn the sign-in form into a
    lookup service for finding out which addresses belong to scholars.

    The offer to register is attached to every refusal for the same reason. An
    invitation that appeared only for unknown addresses would restore exactly
    the signal the shared message removes.

    The one message that does name a specific cause is the deactivation notice,
    and it is safe because it is reached only once the supplied password has
    been checked against the account: whoever reads it already has the
    credentials.
    """
    ctx = {'email': email}

    if not email:
        ctx['error'] = 'Enter the email address you registered with.'
        return ctx
    if not password:
        ctx['error'] = 'Enter your password.'
        return ctx

    account = User.objects.filter(email__iexact=email).first()
    if account is not None and not account.is_active             and account.check_password(password):
        ctx['error'] = (
            'That account has been deactivated. Contact the SDSO office to have '
            'it reopened.'
        )
        return ctx

    ctx['error'] = SIGN_IN_REFUSED
    ctx['error_action'] = 'register'
    return ctx

def logout_view(request):
    """Sign out and return to the public page."""
    logout(request)
    return redirect('/')

def _await_verification(request, user):
    """Show a new registrant that the office has their details."""
    from .models import ActivityLog
    ActivityLog.record(
        user, f'Account registered — awaiting SDSO verification ({user.get_role_display()})',
        verb='create', request=request)
    from django.utils import timezone
    from .middleware import PENDING_EMAIL, PENDING_SINCE
    request.session[PENDING_EMAIL] = user.email
    request.session[PENDING_SINCE] = timezone.now().isoformat()
    return redirect('/register/received/')

def registration_received(request):
    """The page shown after registering."""
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
    """Confirm an email address from a link.

    Confirming does not sign anyone in: the office still reviews every
    registration. It establishes only that the address is reachable.
    """
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
    """Send the confirmation link again, throttled."""
    from . import email_verify
    from .middleware import PENDING_EMAIL
    from urllib.parse import quote

    if request.method != 'POST':
        return redirect('/register/received/')

    email = request.session.get(PENDING_EMAIL, '')

    wait = ratelimit.retry_after(ratelimit.RESEND, request, email)
    if wait is not None:
        return redirect('/register/received/?confirm_error=' + quote(
            ratelimit.wait_message(wait, 'requests for a confirmation link')))
    ratelimit.register_failure(ratelimit.RESEND, request, email)

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
    """Free an email and student number held by a rejected registration.

    Without this a refused applicant cannot register again with their own
    details — the uniqueness checks would find their own dead record.
    """
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
        ActivityLog.record(
            None, (f'Rejected registration replaced by a new one — {held} '
                    f'— original reason: {reason}'),
            verb='reject')
        account.delete()

def _register_context(post=None):
    """Everything the registration form needs to render."""
    import json
    from . import terms
    from .constants import (CIVIL_STATUSES, GENDERS,
                            RELATIONSHIP_TO_STAFF_CHOICES,
                            STAFF_DECLARABLE_LABEL)
    from .models import CHED_TIER_CHOICES, SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return {
        'bipsu_schools': BIPSU_SCHOOLS,
        'bipsu_courses_json': json.dumps(BIPSU_COURSES),
        'civil_statuses': CIVIL_STATUSES,
        'genders': GENDERS,
        'staff_relationships': RELATIONSHIP_TO_STAFF_CHOICES,
        'scholarship_types': declarable_types(),
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
    """Map the posted registration form onto profile fields."""
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
    for name, _label in _REQUIRED_CERTIFICATES:
        if files.get(name):
            fields[name] = files[name]
    return fields

def _decimal_or(raw, fallback):
    """Parse a decimal, falling back when the field will not parse."""
    try:
        return float((raw or '').strip())
    except (TypeError, ValueError):
        return fallback

def _certificate_errors(files):
    """Validate whichever certificates were supplied.

    Absence is reported separately by ``_missing_certificates``; this only
    checks the type and size of what did arrive, so a registrant gets both
    complaints at once rather than one per attempt.
    """
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    errors = []
    for field, label in _REQUIRED_CERTIFICATES:
        upload = files.get(field)
        if upload:
            errors += [f'{label}: {problem}'
                       for problem in _validate_proof(upload, settings_obj)]
    return errors

def _declared_staff_scholarship(p, files):
    """Validate a staff award declared during registration.

    Returns:
        ``(declaration, errors)``, or ``(None, [])`` when none was
        declared.
    """
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

_REQUIRED_ELIGIBILITY = (
    ('shs_gpa', 'SHS Grade Point Average'),
    ('suc_exam_score', 'SUC Admission Exam Score'),
    ('suc_exam_total', 'SUC Admission Exam Score — total items'),
)

_REQUIRED_CERTIFICATES = (
    ('shs_gpa_cert', 'SHS GPA Certificate'),
    ('suc_exam_cert', 'SUC Exam Certificate'),
    ('study_load', 'Certificate of Registration / Study Load'),
)

_REQUIRED_OF_AN_APPLICANT = (
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

def _unanswered_tes(posted, questions):
    """Which TES eligibility questions were left unanswered."""
    return [f'{label} — please answer Yes or No.' for name, label in questions
            if (posted.get(name) or '').strip().casefold() not in ('yes', 'no')]

def _missing_certificates(files, questions):
    """Which required certificates the form did not carry."""
    return [f'{label} is required.' for name, label in questions
            if not files.get(name)]

def _remember_registration_source(request, email):
    """Record where a registration came from, for the office."""
    from .models import SignupSource
    payload = _utm_payload(request)
    if not payload:
        return
    try:
        SignupSource.record(email, 'registration', payload)
    except Exception:
        logger.exception('registration: could not record the signup source for %s', email)

def register_view(request):
    """Create an account, throttled so the form cannot be driven in bulk.

    The throttle counts every submission rather than only the failures. An
    unthrottled register form is a way to mint accounts and to send mail to
    arbitrary addresses on the university's behalf, and both of those are done
    with submissions that succeed.
    """
    if request.method == 'POST':
        p = request.POST
        errors = []
        account_type = p.get('account_type', 'student')

        wait = ratelimit.retry_after(ratelimit.REGISTER, request,
                                     (p.get('email') or '').strip())
        if wait is not None:
            ctx = _register_context(p)
            ctx['errors'] = [ratelimit.wait_message(wait, 'registrations')]
            return render(request, 'register.html', ctx, status=429)
        ratelimit.register_failure(ratelimit.REGISTER, request,
                                   (p.get('email') or '').strip())

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
                errors += _unanswered(p, _REQUIRED_ELIGIBILITY)
                errors += _missing_certificates(request.FILES, _REQUIRED_CERTIFICATES)
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
        _remember_registration_source(request, user.email)

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
            ActivityLog.record(
                user,
                f"Staff account created — "
                f"School ID: {p.get('school_id','—')} | "
                f"School: {staff_school or '—'} | "
                f"Department: {p.get('department','—')} | "
                f"Position: {p.get('position','—')} | "
                f"Contact: {p.get('contact_number','—')}",
                verb='create', request=request, target=user)
            return _await_verification(request, user)

    return render(request, 'register.html', dict(_register_context(), post={}))
