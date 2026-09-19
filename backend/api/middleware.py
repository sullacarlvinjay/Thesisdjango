from datetime import timedelta

from django.contrib.auth import login
from django.middleware.gzip import GZipMiddleware
from django.utils import timezone

ALREADY_COMPRESSED = frozenset({
    'application/pdf',
    'application/zip',
    'application/gzip',
    'application/x-7z-compressed',
    'application/vnd.rar',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
})

COMPRESSIBLE_MEDIA = frozenset({'image/svg+xml', 'image/bmp', 'image/x-icon'})


class SelectiveGZipMiddleware(GZipMiddleware):
    def process_response(self, request, response):
        content_type = (response.get('Content-Type') or '').split(';')[0].strip().lower()
        if content_type not in COMPRESSIBLE_MEDIA:
            if content_type in ALREADY_COMPRESSED:
                return response
            if content_type.startswith(('image/', 'video/', 'audio/', 'font/')):
                return response
        return super().process_response(request, response)

PENDING_EMAIL = 'awaiting_verification_email'
PENDING_SINCE = 'awaiting_verification_since'

AUTO_RELEASE_WINDOW = timedelta(days=3)


def _registered_within_window(request):
    stamp = request.session.get(PENDING_SINCE)
    if not stamp:
        return False
    parsed = timezone.datetime.fromisoformat(stamp)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return timezone.now() - parsed <= AUTO_RELEASE_WINDOW


def _forget(session):
    session.pop(PENDING_EMAIL, None)
    session.pop(PENDING_SINCE, None)


class ApiCacheHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith('/api/'):
            return response
        if response.has_header('Cache-Control'):
            return response
        if request.method in ('GET', 'HEAD') and response.status_code < 400:
            response['Cache-Control'] = 'private, no-cache'
        else:
            response['Cache-Control'] = 'private, no-store'
        return response


class ReleaseVerifiedAccountMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._release(request)
        return self.get_response(request)

    def _release(self, request):
        session = getattr(request, 'session', None)
        if session is None or PENDING_EMAIL not in session:
            return
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            _forget(session)
            return
        if not _registered_within_window(request):
            _forget(session)
            return

        from .models import User
        account = User.objects.filter(email=session[PENDING_EMAIL]).first()
        if account is None or account.awaiting_verification:
            return
        if account.can_sign_in:
            login(request, account)
            _forget(session)
