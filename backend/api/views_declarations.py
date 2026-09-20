"""Review of scholarships declared at registration.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from .models import STUDENT_DETAILS, Scholarship, Application, ScholarshipLinkRequest
import logging
from .views_shared import CHED_ARCHIVE_TIERS

logger = logging.getLogger(__name__)


def pending_declarations():
    """Declarations filed through the portal and awaiting a decision.

    Only ``filed_in_portal`` ones. A declaration made during registration
    is reviewed alongside the account itself, not in this queue, or the
    office would be asked to decide the same thing twice.
    """
    return (ScholarshipLinkRequest.objects
            .select_related('student__user', 'reviewed_by', 'matched_archive',
                            *STUDENT_DETAILS)
            .filter(status='Pending', filed_in_portal=True)
            .order_by('submitted_at', 'pk'))

def declared_scholarships(profile):
    """Awards this student declared at registration, still undecided.

    The other half of :func:`pending_declarations`: these are shown on the
    account verification card, because approving the account and accepting
    what it declared is one decision.
    """
    if not profile:
        return []
    return list(ScholarshipLinkRequest.objects
                .select_related('student__user', *STUDENT_DETAILS)
                .filter(student=profile, status='Pending', filed_in_portal=False)
                .order_by('submitted_at', 'pk'))

def _approve_dependent_staff_declaration(req, reviewer, remarks=''):
    """Record a dependent's staff award once the office accepts it.

    The record is written against the student's own email but marked as a
    dependent, carrying the employee's name and number. It is not the
    employee's award and must not be mistaken for one — see
    ``_staff_application_for`` in ``views_staff``, which excludes these.
    """
    from .models import (ActivityLog, ApplicantRecord, Notification,
                         SystemSettings)
    from django.utils import timezone

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    profile = req.student
    user = profile.user

    app = ApplicantRecord.objects.filter(
        email=user.email, qualified_for='Staff',
        school_year=parsed['sy'], semester=parsed['semester'],
    ).first()
    if app is None:
        app = ApplicantRecord(email=user.email)

    app.full_name = user.get_full_name()
    app.qualified_for = 'Staff'
    app.status = 'Approved'
    app.remarks = remarks
    app.school_year = parsed['sy']
    app.semester = parsed['semester']
    app.term_label = settings_obj.academic_year
    app.barangay = profile.barangay
    app.municipality = profile.municipality
    app.province = profile.province
    app.save()

    app.contact_number = profile.contact_number
    app.date_of_birth = profile.date_of_birth
    app.gender = profile.gender
    app.course = profile.course
    app.year_level = profile.year_level
    app.student_id = profile.student_id
    app.is_nsu_staff = False
    app.is_nsu_dependent = True
    app.staff_name = req.staff_name
    app.staff_employee_id = req.staff_employee_id
    app.relationship_to_staff = req.relationship_to_staff
    app.save()

    was = req.status
    req.status = 'Approved'
    req.remarks = remarks
    req.reviewed_by = reviewer
    req.reviewed_at = timezone.now()
    req.linked_applicant_record = app
    req.save()

    label = req.get_scholarship_type_display()
    Notification.objects.create(
        student=profile, type='success',
        title=f'{label} linked to your account',
        body=(f'Your {label} has been verified for '
              f"{parsed['sy']} {parsed['semester']}, held as a dependent of "
              f'{req.staff_name}.'),
    )
    ActivityLog.record(
        reviewer, (f'Verified the BiPSU Staff Scholarship declared by '
                f'{profile.student_id} as a dependent of {req.staff_name} '
                f'({req.staff_employee_id})'),
        verb='approve', target=req,
        changes={'status': [was, req.status]})
    return app, ''

def approve_declared_scholarship(req, reviewer, archive=None, remarks='', tier=''):
    """Accept a declared award and write it into the records.

    Where an imported row was matched, the declaration is merged into it
    rather than added beside it — the scholar is already on the funder's
    list, and two rows would double-count them in every report.

    Returns:
        ``(award, problem)``. ``problem`` is a sentence for the office
        when the award could not be written.
    """
    from .constants import DEPENDENT_DECLARABLE_TYPE
    from .models import (CHED_TIER_CHOICES, Notification, ActivityLog,
                         SystemSettings)
    from django.utils import timezone

    if req.scholarship_type == DEPENDENT_DECLARABLE_TYPE:
        return _approve_dependent_staff_declaration(req, reviewer, remarks)

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

    was = req.status
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
    ActivityLog.record(
        reviewer, (f'Verified the {label} declared by {profile.student_id}'
                + (f' (merged imported row #{archive.id})' if archive
                   else ' (no imported row matched)')),
        verb='approve', target=req,
        changes={'status': [was, req.status]})
    return app, ''

def reject_declared_scholarship(req, reviewer, remarks):
    """Turn down a declared award and tell the student why."""
    from .models import Notification, ActivityLog
    from django.utils import timezone

    label = req.get_scholarship_type_display()
    was = req.status
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
    ActivityLog.record(
        reviewer, f'Rejected the {label} declared by {req.student.student_id}',
        verb='reject', target=req,
        changes={'status': [was, req.status]})

def _archive_back(stype, tier=''):
    """The archive URL to return to after deciding, tier included."""
    from urllib.parse import quote

    url = f'/vpsea/archives/?type={quote(stype)}'
    return url + (f'&tier={tier}' if tier in CHED_ARCHIVE_TIERS else '')

def declared_staff_scholarship(user):
    """This employee's undecided staff declaration, if any."""
    from .models import StaffScholarshipDeclaration
    if not user:
        return None
    return (StaffScholarshipDeclaration.objects
            .filter(staff_user=user, status='Pending')
            .order_by('-submitted_at').first())

def approve_declared_staff_scholarship(decl, reviewer, remarks=''):
    """Accept an employee's declared staff award.

    Returns:
        ``(award, problem)``. Refuses with a sentence rather than raising
        when the account has no staff profile to record the award against.
    """
    from django.utils import timezone
    from .models import (ActivityLog, ApplicantRecord, StaffProfile,
                         SystemSettings)

    user = decl.staff_user
    staff = StaffProfile.objects.filter(user=user).first()
    if staff is None:
        return None, ('That account has no staff profile, so the award has '
                      'nowhere to be recorded.')

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)

    app = ApplicantRecord.objects.filter(
        email=user.email, qualified_for='Staff',
        school_year=parsed['sy'], semester=parsed['semester'],
    ).first()
    if app is None:
        app = ApplicantRecord(email=user.email)

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

    was = decl.status
    decl.status = 'Approved'
    decl.remarks = remarks
    decl.reviewed_by = reviewer
    decl.reviewed_at = timezone.now()
    decl.linked_application = app
    decl.save()

    ActivityLog.record(
        reviewer, (f'Verified the BiPSU Staff Scholarship declared by '
                f'{user.get_full_name() or user.email} — recorded as an award '
                f"for {parsed['sy']} {parsed['semester']}."),
        verb='approve', target=decl,
        changes={'status': [was, decl.status]})
    return app, ''

def reject_declared_staff_scholarship(decl, reviewer, remarks):
    """Turn down a declared staff award and notify the employee."""
    from django.utils import timezone
    from .models import ActivityLog

    was = decl.status
    decl.status = 'Rejected'
    decl.remarks = remarks
    decl.reviewed_by = reviewer
    decl.reviewed_at = timezone.now()
    decl.save()
    ActivityLog.record(
        reviewer, (f'Turned down the BiPSU Staff Scholarship declared by '
                f'{decl.staff_user.get_full_name() or decl.staff_user.email} — {remarks}'),
        verb='reject', target=decl,
        changes={'status': [was, decl.status]})
