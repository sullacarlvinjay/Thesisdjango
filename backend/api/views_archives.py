"""Scholar records, term rollover and spreadsheet import.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render, redirect
from . import scholar_columns
from .models import STAFF_APPLICATION_DETAILS, STUDENT_DETAILS, StudentProfile, Scholarship, Application, User, ApplicantRecord, BIPSU_SCHOOLS, BIPSU_COURSES, split_ched
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from django.db import transaction
from . import notify
from django.http import HttpResponse
from datetime import date
from io import BytesIO
import logging
from .views_shared import CHED_ARCHIVE_TIERS, COLUMN_HINTS, COLUMN_MAPS, _scholar_groups, _scholars_from_sheet, _vpsea_required
from .views_declarations import _archive_back

logger = logging.getLogger(__name__)


def _archive_candidates(req, label=None):
    """Imported rows a declaration might be claiming.

    Matched loosely on purpose. The office confirms the match by hand, so
    a few extra candidates cost a glance while a missed one leaves a
    scholar recorded twice.
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

UNAWARDED_TAB = 'No Scholarship'

def _unawarded_rows(term_label):
    """Imported scholars nobody has claimed, for the unawarded tab."""
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

def _archive_tabs(archive_types, active_type, active_tier):
    """The tab strip for the archive page."""
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
    """Every term with records for this programme, newest first."""
    from .models import ScholarListImport

    labels = list(
        ScholarListImport.objects.filter(scholarship_type=stype)
        .values_list('term_label', flat=True).distinct().order_by('-term_label')
    )
    if active_label not in labels:
        labels.insert(0, active_label)
    return labels

def _archive_term(request, stype, active_label):
    """The term being viewed, falling back to the active one."""
    labels = _archive_terms(stype, active_label)
    chosen = request.GET.get('sy', active_label)
    return labels, chosen if chosen in labels else active_label

def _archive_records(stype, term_label, tier=None):
    """The scholar records for one programme and term."""
    from .models import ImportedScholar

    imported_rows = list(ImportedScholar.objects.filter(
        scholarship_type=stype, term_label=term_label, claimed_by__isnull=True,
    ).order_by('last_name', 'first_name'))

    if stype in ('Affirmative', 'Staff'):
        scholars = list(ApplicantRecord.objects.filter(
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
    """Scholar records for one programme, by term."""
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
    """Add a scholar record by hand."""
    from .models import (Application, Scholarship, StudentProfile, User,
                         ApplicantRecord, SystemSettings,
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
            while ApplicantRecord.objects.filter(email=email).exists():
                email = f"{base.split('@')[0]}_{counter}@bipsu.edu.ph"
                counter += 1
        ApplicantRecord.objects.create(
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
    """Apply posted edits to a student record."""
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
    """Edit a portal scholar's record."""
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
    """Delete a student record and the account behind it."""
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
    identity = ActivityLog.identify(profile)
    profile.user.delete()
    ActivityLog.record(
        request.user, f'Deleted the student record for {who} ({sid})',
        verb='delete', request=request, identity=identity)
    return redirect(f'{back}&deleted=1')

@_vpsea_required
def vpsea_archive_edit(request, pk):
    """Edit an imported scholar row."""
    from .models import Application, ApplicantRecord
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    p = request.POST
    stype = p.get('scholarship_type', 'Academic')
    back = _archive_back(stype, p.get('tier', ''))
    is_aff = stype in ('Affirmative', 'Staff')

    if is_aff:
        try:
            obj = ApplicantRecord.objects.get(pk=pk)
        except ApplicantRecord.DoesNotExist:
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
    """Delete an imported scholar row."""
    from .models import Application, ApplicantRecord
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('scholarship_type', 'Academic')
    back = _archive_back(stype, request.POST.get('tier', ''))
    if stype in ('Affirmative', 'Staff'):
        ApplicantRecord.objects.filter(pk=pk).delete()
    else:
        Application.objects.filter(pk=pk).delete()
    return redirect(f'{back}&deleted=1')

@_vpsea_required
def vpsea_new_semester(request):
    """Close the current term and open the next.

    Every programme's list is written to a spreadsheet first, so the term
    just closed can still be reported on afterwards. That file is the only
    record of it once the live tables move on.
    """
    from .models import (
        SystemSettings, ScholarListImport, ActivityLog, Application,
        ApplicantRecord, ImportedScholar,
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
        """Build the scholar spreadsheet for download."""
        col_map = COLUMN_MAPS.get(scholarship_type, COLUMN_MAPS['CoScho'])
        hint = COLUMN_HINTS.get(scholarship_type, COLUMN_HINTS['CoScho'])
        header = [h.strip() for h in hint.split('|')]

        if scholarship_type in ('Affirmative', 'Staff'):
            qs = ApplicantRecord.objects.filter(
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

    ActivityLog.record(
        request.user, f'New semester started: {label} ({parsed["sy"]} {parsed["semester"]}). '
               f'Saved lists for {created} scholarship types under {outgoing_label}.',
        verb='create', request=request)
    return redirect(f'/vpsea/archives/?type={stype}')

@_vpsea_required
def vpsea_undo_semester(request):
    """Step the active term back after a rollover.

    The rollover is the most consequential action in the office's year,
    and it is one button. This is the way back from having pressed it by
    mistake.
    """
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
    ActivityLog.record(
        request.user, f'Semester undone from {old_label} back to {prev_label} ({parsed["sy"]} {parsed["semester"]}).',
        verb='update', request=request)
    return redirect(f'/vpsea/archives/?type={stype}')

def _rollover_fields(record, programme_name=''):
    """The column layout for a rollover spreadsheet."""
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

    if isinstance(record, ApplicantRecord):
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
    """Delete an import and every scholar row it created.

    Returns:
        ``(removed, type, label)`` — the count is reported to the office,
        because deleting an import silently taking a hundred scholars with
        it is not something to discover later.
    """
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
    """Delete one imported scholar."""
    from .models import ImportedScholar, ActivityLog
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('scholarship_type', 'Academic')
    row = ImportedScholar.objects.filter(pk=pk).first()
    if not row:
        return redirect(f'/vpsea/archives/?type={stype}')
    label = f'{row.full_name} ({row.scholarship_type} {row.term_label})'
    identity = ActivityLog.identify(row)
    row.delete()
    ActivityLog.record(
        request.user, f'Deleted imported scholar {label}.',
        verb='delete', request=request, identity=identity)
    return redirect(f'/vpsea/archives/?type={stype}&deleted=1')

@_vpsea_required
def vpsea_rollover_delete(request, pk):
    """Delete a filed import and its scholars."""
    from .models import ScholarListImport, ActivityLog
    if request.method != 'POST':
        return redirect('/vpsea/archives/')
    stype = request.POST.get('type', 'Academic')
    try:
        r = ScholarListImport.objects.get(pk=pk)
    except ScholarListImport.DoesNotExist:
        return redirect(f'/vpsea/archives/?type={stype}')
    identity = ActivityLog.identify(r)
    removed, imported_type, label = _delete_import_with_scholars(r)
    ActivityLog.record(
        request.user, f'Deleted the {imported_type} import for "{label}" and the '
               f'{removed} scholar row(s) it had created.',
        verb='delete', request=request, identity=identity,
        changes={'scholar_rows_removed': [removed, 0]})
    return redirect(f'/vpsea/archives/?type={stype}')

@_vpsea_required
def vpsea_archive_import(request):
    """Import a scholar list from a spreadsheet."""
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

        ActivityLog.record(
            request.user, f'Imported {file.name} ({created} rows) for {stype} as "{rollover_label}"',
            verb='import', request=request)
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
    """Download the current scholar table as a spreadsheet."""
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
        """Write the heading row for a section of the spreadsheet."""
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
            for index, (column, cell_value) in enumerate(zip(columns, row['cells'], strict=False), 2):
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
    """A worksheet name Excel will accept."""
    return (title.translate(_BAD_SHEET_CHARS).strip() or 'Scholars')[:31]

def _rollover_workbook(field_file):
    """Open a filed spreadsheet, from disk or object storage."""
    with field_file.open('rb') as handle:
        return openpyxl.load_workbook(BytesIO(handle.read()))

STUDENT_RECORD_FIELDS = (
    'first_name', 'last_name', 'email', 'password', 'student_id',
    'middle_name', 'suffix', 'birth_place', 'civil_status',
    'date_of_birth', 'gender', 'contact_number',
    'barangay', 'municipality', 'province',
    'school', 'course', 'level', 'department', 'curriculum', 'year_level',
    'learner_ref_no', 'entry_period', 'entry_date', 'exam_score', 'gwa',
    'family_income',
)

def _save_column_values(request, base_url, portal='vpsea'):
    """Save edited custom-column values from the table."""
    from urllib.parse import urlencode

    from .models import ApplicantRecord, Application, ImportedScholar

    stype = request.POST.get('type', '')
    query = {k: v for k, v in (('type', stype), ('tier', request.POST.get('tier', '')),
                               ('sy', request.POST.get('sy', ''))) if v}

    def back(**extra):
        """The archive URL to return to."""
        return f'{base_url}?{urlencode({**query, **extra})}' if query or extra else base_url

    if request.method != 'POST':
        return redirect(back())

    programme = Scholarship.objects.filter(type=stype).first()
    custom = {c['key']: c for c in scholar_columns.resolve(programme, stype, portal)
              if c['custom']}

    models_by_kind = {
        'award': Application,
        'imported': ImportedScholar,
        'staff': ApplicantRecord,
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
    """Choose which columns a programme's table shows."""
    return _save_column_values(request, '/vpsea/archives/')
