from datetime import timedelta

from django.contrib.auth import login
from django.utils import timezone

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
