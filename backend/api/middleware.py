"""Request-time hooks that keep account verification from being a chore.

Registration deliberately does not sign anyone in — the SDSO has to release the
account first. But the person is left holding a browser that knows exactly who
they are, so when the decision finally lands there is no reason to make them
find the login page and retype the password they chose minutes earlier.
"""
from datetime import timedelta

from django.contrib.auth import login
from django.utils import timezone

# Session keys written by the registration form.
PENDING_EMAIL = 'awaiting_verification_email'
PENDING_SINCE = 'awaiting_verification_since'

# How long a registration keeps the right to be let in without typing a
# password. It covers the realistic wait for the office to get to the queue.
# Past it the browser has probably changed hands — a shared lab PC should not
# sign a stranger in as whoever registered on it last week.
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
    """Sign a just-registered visitor in the moment the SDSO verifies them.

    Costs a dict lookup for everyone else: only a browser that went through the
    registration form carries the session key that makes this do any work, and
    the key is dropped as soon as the account is released or the window closes.

    Must sit after AuthenticationMiddleware, which is what puts ``request.user``
    there for the check below.
    """

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
            return              # still in the queue; nothing to do yet
        if account.can_sign_in:
            login(request, account)
            _forget(session)
        # A rejected account keeps the key so the 'registration received' page
        # can tell them what the office said. The window above bounds how long.
