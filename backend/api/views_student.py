"""The student portal.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import ActivityLog, StudentProfile, Scholarship, Application, Notification, Announcement, AcademicRenewal, ScholarshipLinkRequest, BIPSU_SCHOOLS, BIPSU_COURSES
from . import notify
import logging
from .views_shared import _declaration_slots, _declared_scholarships, _disability_answer, _disability_fields, _positive_int, _tristate, _unanswered, _validate_proof, application_window_reason, can_hold_alongside, declarable_types, held_scholarship_types, renewal_window_reason

logger = logging.getLogger(__name__)


def _scholarship_records(profile):
    """Every award and declaration on this student's file."""
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

GWA_REQUIRED = ('Enter your GWA before sending this application. The office '
                'ranks Academic applicants by it, so it cannot read one that '
                'has none — and it has to fall between 1.00 and 5.00.')

_APPLY_ACADEMIC_TYPED = (
    ('course', 'Course'),
    ('elementary', 'Elementary School'),
    ('highschool', 'High School'),
    ('last_school', 'Last School Attended'),
    ('father_name', "Father's Name"),
    ('father_occupation', "Father's Occupation"),
    ('mother_name', "Mother's Name"),
    ('mother_occupation', "Mother's Occupation"),
    ('semester', 'Semester'),
    ('school_year', 'School Year'),
)

_APPLY_ACADEMIC_FROM_PROFILE = (
    ('student_id', 'Student Number'),
    ('full_name', 'Name'),
    ('date_of_birth', 'Birth Date'),
    ('gender', 'Gender'),
    ('contact_number', 'Contact Number'),
    ('address', 'Address'),
)

_APPLY_ACADEMIC_DOCUMENTS = (
    ('doc_certificate_of_grades', 'Certificate Of Grades'),
    ('doc_certificate_of_enrollment', 'Certificate Of Enrollment'),
    ('doc_prospectus', 'Prospectus'),
    ('doc_id_photo', 'Id Photo'),
    ('doc_application_form', 'Application Form'),
)

def _missing_from_profile(profile):
    """Profile fields an application needs that are not filled in."""
    return [label for name, label in _APPLY_ACADEMIC_FROM_PROFILE
            if not str(getattr(profile, name, '') or '').strip()]

def _missing_documents(files, editing):
    """Required documents this submission did not carry."""
    on_file = (set(editing.documents.values_list('name', flat=True))
               if editing else set())
    return [f'{label} is required.' for field, label in _APPLY_ACADEMIC_DOCUMENTS
            if not files.get(field) and label not in on_file]

def _apply_academic_errors(request, profile, editing):
    """Validate an academic scholarship application."""
    errors = _unanswered(request.POST, _APPLY_ACADEMIC_TYPED)
    if _parse_gwa(request.POST.get('gwa')) is None:
        errors.append(GWA_REQUIRED)
    missing = _missing_from_profile(profile)
    if missing:
        errors.append(
            'Your student record has no ' + ', '.join(missing) + '. The form '
            'sends those straight from your record, so open My Profile, fill '
            'them in there, and come back to this page.')
    errors += _missing_documents(request.FILES, editing)
    return errors

def _apply_academic_values(profile, term, posted=None):
    """Map the posted application form onto the profile."""
    names = [name for name, _label in _APPLY_ACADEMIC_TYPED]
    if posted is not None:
        values = {name: (posted.get(name) or '').strip() for name in names}
        values['gwa'] = (posted.get('gwa') or '').strip()
        return values
    values = {name: (getattr(profile, name, '') or '') if profile else ''
              for name in names}
    values['semester'] = term['semester']
    values['school_year'] = term['sy']
    values['gwa'] = _gwa_for_display(profile.gwa if profile else 0)
    return values

def _parse_gwa(raw):
    """Parse a GWA, or ``None`` if it is not a usable number."""
    try:
        value = float((raw or '').strip())
    except (TypeError, ValueError):
        return None
    return value if 1.0 <= value <= 5.0 else None

def _gwa_for_display(value):
    """A GWA formatted for a form field."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ''
    return number if 1.0 <= number <= 5.0 else ''

def scholarship_block_reason(profile, wanted, label):
    """Why this student may not apply for a programme, or ''.

    One place for every reason — already held, conflicting award, window
    closed — so the page and the POST handler cannot disagree about
    whether someone is allowed.
    """
    shut = application_window_reason(wanted)
    if shut:
        return shut
    held = held_scholarship_types(profile)
    if can_hold_alongside(held, wanted):
        return ''
    if wanted in held:
        return f'You already hold the {label}. There is nothing to apply for.'
    from .constants import scholarship_type_labels
    display = scholarship_type_labels()
    names = ', '.join(sorted(display.get(t, t) for t in held))
    return (f'You are already enrolled in {names}. Each programme is held on '
            'its own — a scholar may not be on two at once.')

def _is_enrolled(profile):
    """Whether this profile records a current enrolment."""
    return bool(held_scholarship_types(profile))

def _system_settings():
    """The settings row, created if this is a fresh database."""
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return settings_obj

@login_required(login_url='/login/')
def student_dashboard(request):
    """The student portal's landing page."""
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
    """Apply for an academic scholarship."""
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
    errors, posted = [], None
    if request.method == 'POST':
        scholarship = Scholarship.objects.filter(type='Academic').first()
        if not (scholarship and profile):
            return redirect('/student/applications/')
        errors = _apply_academic_errors(request, profile, editing)
        if errors:
            posted = request.POST
        else:
            profile.gwa = _parse_gwa(request.POST.get('gwa'))
            profile.save(update_fields=['gwa'])
            if editing:
                app = editing
                app.form_data = request.POST.dict()
                app.status = 'Pending Validation'
                app.remarks = ''
                app.save()
                resubmitted = True
            else:
                app = Application.objects.create(
                    student=profile, scholarship=scholarship,
                    status='Pending Validation',
                    form_data=request.POST.dict()
                )
                resubmitted = False
            ActivityLog.record(
                request.user,
                f'{"Resubmitted" if resubmitted else "Applied"} for '
                f'{scholarship.name} ({app.term_label})',
                verb='update' if resubmitted else 'create',
                target=app, request=request)
            for field, label in _APPLY_ACADEMIC_DOCUMENTS:
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
        'errors': errors,
        'form': _apply_academic_values(profile, term, posted),
    })

@login_required(login_url='/login/')
def student_applications(request):
    """A student's own applications and their standing."""
    profile = StudentProfile.objects.filter(user=request.user).first()
    applications = Application.objects.filter(student=profile).select_related('scholarship') if profile else Application.objects.none()
    return render(request, 'student/applications.html', {
        'applications': applications,
        'enrolled': _is_enrolled(profile),
    })

def declaration_blocked_reason(profile):
    """Why this student may not declare an award, or ''."""
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
        from .constants import scholarship_type_labels
        labels = scholarship_type_labels()
        named = ', '.join(sorted(labels.get(t, t)
                                 for t in held_scholarship_types(profile)))
        return (f'This account already holds the {named}. Every programme here '
                'is exclusive, so there is nothing to add beside it. If that is '
                'no longer right — an award that ended, or one recorded in '
                'error — the SDSO corrects it from their side.')
    return ''

@login_required(login_url='/login/')
def student_notifications(request):
    """Notifications for a student."""
    profile = StudentProfile.objects.filter(user=request.user).first()
    notifications = Notification.objects.filter(student=profile).order_by('-created_at') if profile else Notification.objects.none()
    return render(request, 'student/notifications.html', {'notifications': notifications, 'enrolled': _is_enrolled(profile)})

def _renewable_programmes(profile):
    """Programmes this student may renew this term."""
    from .constants import scholarship_type_labels
    labels = scholarship_type_labels()
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
    """File a renewal for an academic scholarship."""
    from .models import SystemSettings
    profile = StudentProfile.objects.filter(user=request.user).first()
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    programmes = _renewable_programmes(profile)
    open_programmes = [p for p in programmes if p['open']]

    renewals = (AcademicRenewal.objects.filter(student=profile)
                .order_by('-submitted_at') if profile else [])

    def page(**extra):
        """Render the profile page with the current context."""
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
            renewal = AcademicRenewal.objects.create(
                student=profile, certificate_of_grades=cog,
                certificate_of_enrollment=coe, scholarship_type=chosen['type'])
            ActivityLog.record(
                request.user,
                f"Submitted a {chosen['type']} renewal for "
                f'{renewal.term_label}',
                verb='create', target=renewal, request=request)
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

PROFILE_UPLOADS = (
    ('photo', 'Profile photo'),
    ('shs_gpa_cert', 'SHS GPA Certificate'),
    ('suc_exam_cert', 'SUC Exam Certificate'),
)


def _uploaded_file_errors(files):
    """Check every file this page accepts, on the server.

    The model fields carry ``validate_document``, but a validator only runs
    during ``full_clean()`` and this view assigns straight to the field and
    saves. Nothing was checking type or size, which left the ``accept``
    attribute on the input as the only gate — and that is one line of
    devtools away from being removed.

    Args:
        files: ``request.FILES``.

    Returns:
        A list of messages, empty when every supplied file is acceptable.
    """
    from .models import SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    problems = []
    for field, label in PROFILE_UPLOADS:
        uploaded = files.get(field)
        if not uploaded:
            continue
        problems += [f'{label}: {problem}'
                     for problem in _validate_proof(uploaded, settings_obj)]
    return problems


PROFILE_TRISTATE_FIELDS = (
    'highschool_is_public', 'is_from_depressed_area',
    'is_listahanan_household', 'is_4ps_beneficiary', 'has_previous_degree',
    'is_solo_parent_dependent',
)


def _optional_float(raw):
    """A float from a posted string, or ``None`` where it will not convert."""
    text = (raw or '').strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _apply_write_once_fields(profile, posted):
    """Fill the answers a student may set but not later change.

    Locked once answered, because these are the details the office verified
    on the registration documents. A student correcting one goes through the
    office rather than through this form.
    """
    if not profile.middle_name:
        profile.middle_name = posted.get('middle_name', '').strip()
    if not profile.civil_status:
        profile.civil_status = posted.get('civil_status', profile.civil_status)
    if not profile.birth_place:
        profile.birth_place = posted.get('birth_place', profile.birth_place).strip()

    if not (profile.elementary and profile.highschool and profile.last_school):
        profile.elementary = posted.get('elementary', profile.elementary)
        profile.highschool = posted.get('highschool', profile.highschool)
        profile.last_school = posted.get('last_school', profile.last_school)

    if not (profile.father_last_name and profile.father_first_name
            and profile.mother_last_name and profile.mother_first_name):
        for parent in ('father', 'mother'):
            for part in ('last_name', 'first_name', 'middle_name'):
                field = f'{parent}_{part}'
                setattr(profile, field,
                        posted.get(field, getattr(profile, field)).strip())
        profile.father_occupation = posted.get(
            'father_occupation', profile.father_occupation)
        profile.mother_occupation = posted.get(
            'mother_occupation', profile.mother_occupation)

    if not (profile.barangay and profile.municipality and profile.province):
        profile.barangay = posted.get('barangay', profile.barangay)
        profile.municipality = posted.get('municipality', profile.municipality)
        profile.province = posted.get('province', profile.province)


def _apply_eligibility_fields(profile, posted):
    """Fill the answers the ranking rules read, which stay editable."""
    profile.suffix = posted.get('suffix', profile.suffix).strip()
    profile.family_income = float(
        posted.get('family_income', profile.family_income)
        or profile.family_income)
    profile.indigenous_group = posted.get(
        'indigenous_group', profile.indigenous_group)
    profile.citizenship = posted.get('citizenship', profile.citizenship)
    profile.household_size = _positive_int(
        posted.get('household_size'), profile.household_size)
    profile.year_first_enrolled = _positive_int(
        posted.get('year_first_enrolled'), profile.year_first_enrolled)

    for field in PROFILE_TRISTATE_FIELDS:
        setattr(profile, field,
                _tristate(posted.get(field), getattr(profile, field)))

    shs = _optional_float(posted.get('shs_gpa'))
    if shs is not None:
        profile.shs_gpa = shs

    if (posted.get('suc_exam_total') or '').strip():
        total = _optional_float(posted.get('suc_exam_total'))
        if total is not None:
            profile.suc_exam_total = total if total > 0 else None
    else:
        profile.suc_exam_total = None

    score = _optional_float(posted.get('suc_exam_score'))
    if score is not None:
        profile.suc_exam_score = score

    profile.is_tes_beneficiary = 'is_tes_beneficiary' in posted


def _attach_profile_uploads(profile, user, files):
    """Save whichever certificates and photo the form carried."""
    if files.get('shs_gpa_cert'):
        profile.shs_gpa_cert = files['shs_gpa_cert']
    if files.get('suc_exam_cert'):
        profile.suc_exam_cert = files['suc_exam_cert']
    if files.get('photo'):
        user.photo = files['photo']
        user.save(update_fields=['photo'])


def _portal_declarations(profile, posted, files):
    """Scholarships declared from the portal, and what is wrong with them.

    Returns:
        ``(declarations, errors)``.
    """
    if declaration_blocked_reason(profile):
        return [], []

    declarations, errors = _declared_scholarships(posted, files)
    held = held_scholarship_types(profile)
    for declared in declarations:
        if can_hold_alongside(held, declared['scholarship_type']):
            continue
        from .constants import scholarship_type_labels

        label = scholarship_type_labels().get(
            declared['scholarship_type'], declared['scholarship_type'])
        errors.append(f'The {label} cannot be added alongside what '
                      'this account already holds. Reload this page '
                      'to see what is still open to you.')
    return declarations, errors


def _save_student_profile(request, profile):
    """Apply a posted profile edit.

    Returns:
        ``(errors, declared_count)``. Nothing is written when there are
        errors, so a rejected form leaves the record exactly as it was.
    """
    posted = request.POST
    errors = _uploaded_file_errors(request.FILES)

    _apply_write_once_fields(profile, posted)
    _apply_eligibility_fields(profile, posted)

    disability, problem = _disability_answer(posted)
    if problem:
        errors.append(problem)
    else:
        profile.disability_type = disability

    declarations, declaration_errors = _portal_declarations(
        profile, posted, request.FILES)
    errors.extend(declaration_errors)

    if errors:
        return errors, 0

    _attach_profile_uploads(profile, profile.user, request.FILES)
    profile.save()
    ActivityLog.record(
        request.user, 'Updated their own student profile',
        verb='update', target=profile, request=request)
    for declared in declarations:
        request_row = ScholarshipLinkRequest.objects.create(
            student=profile, filed_in_portal=True, **declared)
        ActivityLog.record(
            request.user,
            f"Declared a {declared['scholarship_type']} award granted elsewhere",
            verb='create', target=request_row, request=request)
    if declarations:
        notify.scholarship_added(profile, declarations)
    return [], len(declarations)


PROFILE_LOCKS = {
    'address_locked': ('barangay', 'municipality', 'province'),
    'middle_name_locked': ('middle_name',),
    'civil_status_locked': ('civil_status',),
    'birth_place_locked': ('birth_place',),
    'education_locked': ('elementary', 'highschool', 'last_school'),
    'family_locked': ('father_last_name', 'father_first_name',
                      'mother_last_name', 'mother_first_name'),
}


def _profile_locks(profile):
    """Which write-once sections are already answered and closed.

    A section locks once every field in it is filled, which is the same rule
    ``_apply_write_once_fields`` saves by. Reading it off one table means the
    form and the save cannot disagree about which fields are still editable.
    """
    return {
        name: bool(profile) and all(getattr(profile, field) for field in fields)
        for name, fields in PROFILE_LOCKS.items()
    }


@login_required(login_url='/login/')
def student_profile(request):
    """View and update a student's own profile."""
    import json

    from .constants import CIVIL_STATUSES
    from .models import CHED_TIER_CHOICES

    profile = StudentProfile.objects.filter(user=request.user).first()
    errors = []
    saved = False
    declared_count = 0

    if request.method == 'POST' and profile:
        errors, declared_count = _save_student_profile(request, profile)
        saved = not errors

    return render(request, 'student/profile.html', {
        'profile': profile, 'errors': errors, 'saved': saved,
        'enrolled': _is_enrolled(profile),
        'bipsu_schools': BIPSU_SCHOOLS,
        'bipsu_courses_json': json.dumps(BIPSU_COURSES),
        **_profile_locks(profile),
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
