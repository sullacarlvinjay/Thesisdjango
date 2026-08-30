"""Access control for uploaded files.

Until now /media/ was wired through ``django.conf.urls.static.static()``. That
helper does two unhelpful things at once: it serves every upload to anyone who
knows the URL, and it returns nothing at all when DEBUG is off — so the document
viewer would have died on the first production deploy anyway.

This module replaces it. Every request for an upload is resolved back to the
record that owns it and checked against the person asking.

The rule is deliberately strict: a path that cannot be traced to an owner is
refused rather than served. New FileFields are therefore invisible until they
are added to ``_OWNER_RESOLVERS`` below, which is the failure that gets noticed
in testing instead of the one that leaks a document.
"""

import posixpath

from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.http import FileResponse, Http404
from django.utils.cache import patch_cache_control

# Branding, not student data. The login and landing pages reference these
# before anyone has signed in, so they cannot require a session.
PUBLIC_PREFIXES = ('logos/', 'backgrounds/')

# Roles that review other people's applications for a living.
OFFICE_ROLES = frozenset({'vpsea', 'unifast', 'super'})


# How each model reaches the User that owns its files.
_STUDENT_USER_PATH = {
    'StudentProfile': 'user_id',
    'ApplicationDocument': 'application__student__user_id',
    'AcademicRenewal': 'student__user_id',
    'ScholarshipLinkRequest': 'student__user_id',
    'StaffProfile': 'user_id',
    'StaffRenewal': 'staff_user_id',
}

# upload_to prefix -> (model, field name). Order matters only in that the
# longest matching prefix wins, which _resolve_owners handles.
_OWNER_RESOLVERS = {
    'profile/shs_cert/':   [('StudentProfile', 'shs_gpa_cert')],
    'profile/suc_cert/':   [('StudentProfile', 'suc_exam_cert')],
    'documents/':          [('ApplicationDocument', 'file')],
    'renewals/academic/':  [('AcademicRenewal', 'certificate_of_grades'),
                            ('AcademicRenewal', 'certificate_of_enrollment')],
    'renewals/staff/':     [('StaffRenewal', 'supporting_document')],
    'staff/appointment/':  [('StaffProfile', 'appointment_paper')],
    'link_requests/':      [('ScholarshipLinkRequest', 'proof_document')],
}

# Office-generated artefacts: imports and rendered masterlists. These belong to
# no applicant, so no student ever has a reason to read one.
_OFFICE_ONLY_PREFIXES = ('rollovers/', 'masterlist/')

# Applications submitted outside the student portal carry an email rather than
# an account, so they are matched by address instead of by user id.
_EMAIL_OWNED = {
    'affirmative/shs/': ('AffirmativeStaffApplication', 'shs_certificate'),
    'affirmative/suc/': ('AffirmativeStaffApplication', 'suc_exam_certificate'),
}


def _normalise(path):
    """Reject anything that tries to climb out of MEDIA_ROOT."""
    clean = posixpath.normpath(path.replace('\\', '/')).lstrip('/')
    if clean.startswith('../') or clean == '..' or clean.startswith('/'):
        raise Http404
    return clean


def _owner_user_ids(path):
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

    # Unrecognised prefix — refuse rather than guess.
    return False


def serve_media(request, path):
    """Serve an upload, but only to someone entitled to read it.

    404 rather than 403 throughout: telling an unauthorised visitor that a file
    exists is itself a small leak, and the document viewer has no use for the
    distinction.

    The two halves come from different places on purpose. Branding ships with
    the code and lives on disk, so it is read from MEDIA_ROOT and may be cached;
    uploads belong to people, so they come from the configured storage backend
    — Supabase Storage in production — and are never cached by anything in
    between.
    """
    path = _normalise(path)

    if path.startswith(PUBLIC_PREFIXES):
        # FileSystemStorage explicitly, not default_storage: with Supabase
        # Storage configured, default_storage points at a bucket that has never
        # held the university's logos and never should.
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
