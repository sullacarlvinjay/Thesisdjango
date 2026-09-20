"""Serving uploaded files, with an access check on each one.

Branding is public. Everything else is a scholar's document, and is served only
to its owner or to the office. A refused request gets 404 rather than 403,
because a 403 confirms the file exists — and for a document named after a
person, that is itself a disclosure.
"""

import posixpath

from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.http import FileResponse, Http404
from django.utils.cache import patch_cache_control

PUBLIC_PREFIXES = ('logos/', 'backgrounds/')

OFFICE_ROLES = frozenset({'vpsea'})


_STUDENT_USER_PATH = {
    'StudentProfile': 'user_id',
    'ApplicationDocument': 'application__student__user_id',
    'AcademicRenewal': 'student__user_id',
    'ScholarshipLinkRequest': 'student__user_id',
    'StaffProfile': 'user_id',
    'StaffRenewal': 'staff_user_id',
}

_OWNER_RESOLVERS = {
    'profile/shs_cert/':   [('StudentProfile', 'affirmative_eligibility__shs_gpa_cert')],
    'profile/suc_cert/':   [('StudentProfile', 'affirmative_eligibility__suc_exam_cert')],
    'profile/study_load/': [('StudentProfile', 'enrollment__study_load')],
    'documents/':          [('ApplicationDocument', 'file')],
    'renewals/academic/':  [('AcademicRenewal', 'certificate_of_grades'),
                            ('AcademicRenewal', 'certificate_of_enrollment')],
    'renewals/staff/':     [('StaffRenewal', 'supporting_document')],
    'staff/appointment/':  [('StaffProfile', 'employment__appointment_paper')],
    'link_requests/':      [('ScholarshipLinkRequest', 'proof_document')],
}

_OFFICE_ONLY_PREFIXES = ('rollovers/', 'masterlist/')

_EMAIL_OWNED = {
    'affirmative/shs/': ('ApplicantRecord', 'affirmative_eligibility__shs_certificate'),
    'affirmative/suc/': ('ApplicantRecord', 'affirmative_eligibility__suc_exam_certificate'),
}


def _normalise(path):
    """Reduce a requested path to a safe relative one, or refuse it.

    Traversal is rejected here rather than filtered, because a request
    that tried to climb out of the media root is not one to serve a
    corrected version of.
    """
    clean = posixpath.normpath(path.replace('\\', '/')).lstrip('/')
    if clean.startswith('../') or clean == '..' or clean.startswith('/'):
        raise Http404
    return clean


def _owner_user_ids(path):
    """Account IDs allowed to read this file, or ``None`` if unknown.

    ``None`` means no resolver claims the prefix, which the caller must
    treat as "refuse", not as "no restriction".
    """
    from django.apps import apps
    for prefix, pairs in _OWNER_RESOLVERS.items():
        if not path.startswith(prefix):
            continue
        owners = set()
        for model_name, field in pairs:
            model = apps.get_model('api', model_name)
            owners |= set(
                model.objects.filter(**{field: path})
                .values_list(_STUDENT_USER_PATH[model_name], flat=True)
            )
        return {uid for uid in owners if uid is not None}
    return None


def _owner_emails(path):
    """Addresses allowed to read this file, or ``None`` if unknown.

    Affirmative and staff records belong to people who often have no
    portal account, so ownership is matched on the address the record
    carries rather than on a foreign key.
    """
    from django.apps import apps
    for prefix, (model_name, field) in _EMAIL_OWNED.items():
        if not path.startswith(prefix):
            continue
        model = apps.get_model('api', model_name)
        return {
            email.lower()
            for email in model.objects.filter(**{field: path})
                                      .values_list('email', flat=True)
            if email
        }
    return None


def _may_read(user, path):
    """Whether this user may read this path.

    Refuses by default. The office sees everything; everyone else sees
    only files an owner resolver ties to them, and the office-only
    prefixes — imports and masterlists, which are lists of other people —
    are closed to applicants outright.
    """
    if not user.is_authenticated:
        return False
    if user.role in OFFICE_ROLES or user.is_superuser:
        return True
    if path.startswith(_OFFICE_ONLY_PREFIXES):
        return False

    owners = _owner_user_ids(path)
    if owners is not None:
        return user.id in owners

    emails = _owner_emails(path)
    if emails is not None:
        return bool(user.email) and user.email.lower() in emails

    return False


def serve_media(request, path):
    """Serve an uploaded file, after checking who is asking.

    Branding is public and cached for a week. Everything else is a scholar
    document: checked against the requester, then sent with ``no-store``
    so it does not sit in a shared browser cache.

    A file the caller may not read raises 404, not 403. A 403 would
    confirm the file exists, which for a document named after a person is
    itself a disclosure.
    """
    path = _normalise(path)

    if path.startswith(PUBLIC_PREFIXES):
        branding = FileSystemStorage(location=settings.MEDIA_ROOT)
        if not branding.exists(path):
            raise Http404
        response = FileResponse(branding.open(path, 'rb'))
        patch_cache_control(response, public=True, max_age=60 * 60 * 24 * 7)
        return response

    if not _may_read(request.user, path):
        raise Http404

    if not default_storage.exists(path):
        raise Http404

    response = FileResponse(default_storage.open(path, 'rb'))
    patch_cache_control(response, private=True, max_age=0, no_store=True)
    return response
