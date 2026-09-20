"""Request and response middleware.

Selective compression, cache headers for the API, and releasing an account the
office has just approved so a waiting registrant is not left staring at a page
that will never change on its own.
"""

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
    """Gzip, but not over already-compressed bytes.

    Compressing a PDF, a spreadsheet or a JPEG spends CPU to make the
    response slightly larger. SVG and BMP are the exceptions worth
    compressing, so they are allowed through by name.
    """
    def process_response(self, request, response):
        """Compress unless the body is already compressed."""
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
    """Whether this browser's pending registration is still recent.

    Bounds how long an unverified address is remembered, so a shared
    machine does not sign someone in days later.
    """
    stamp = request.session.get(PENDING_SINCE)
    if not stamp:
        return False
    parsed = timezone.datetime.fromisoformat(stamp)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return timezone.now() - parsed <= AUTO_RELEASE_WINDOW


def _forget(session):
    """Drop the pending-verification marks from the session."""
    session.pop(PENDING_EMAIL, None)
    session.pop(PENDING_SINCE, None)


class ApiCacheHeadersMiddleware:
    """Keep API responses out of caches.

    Every endpoint is behind a token and most return one person's data, so
    nothing here is safe for a shared cache to hold.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """Add cache headers to ``/api/`` responses."""
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
    """Sign someone in the moment the office approves them.

    Without this a registrant who left the tab open sees the "waiting for
    verification" page indefinitely and has no way to know it changed.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """Release the account, then handle the request."""
        self._release(request)
        return self.get_response(request)

    def _release(self, request):
        """Sign in a remembered account once it can sign in.

        Gives up in every doubtful case — no session mark, already signed in,
        the window elapsed, the account still pending — because signing the
        wrong person in is far worse than making them type a password.
        """
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
