import posixpath

from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.http import FileResponse, Http404
from django.utils.cache import patch_cache_control

PUBLIC_PREFIXES = ('logos/', 'backgrounds/')

OFFICE_ROLES = frozenset({'vpsea', 'super'})


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
    'documents/':          [('ApplicationDocument', 'file')],
    'renewals/academic/':  [('AcademicRenewal', 'certificate_of_grades'),
                            ('AcademicRenewal', 'certificate_of_enrollment')],
    'renewals/staff/':     [('StaffRenewal', 'supporting_document')],
    'staff/appointment/':  [('StaffProfile', 'employment__appointment_paper')],
    'link_requests/':      [('ScholarshipLinkRequest', 'proof_document')],
}

_OFFICE_ONLY_PREFIXES = ('rollovers/', 'masterlist/')

_EMAIL_OWNED = {
    'affirmative/shs/': ('AffirmativeStaffApplication', 'affirmative_eligibility__shs_certificate'),
    'affirmative/suc/': ('AffirmativeStaffApplication', 'affirmative_eligibility__suc_exam_certificate'),
}


def _normalise(path):
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

    return False


def serve_media(request, path):
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
