"""Fixed-window throttling for the endpoints that accept credentials.

Tallies live in the ordinary Django cache rather than in a table. A throttle
that wrote a row per attempt would hand an attacker a cheap way to grow the
database, which is the opposite of what it is for.

Every credential endpoint is counted twice: once against the caller's address
and once against the account being named. The address counter slows a single
machine working through many accounts; the account counter slows a botnet
working through one account, which no address counter can see. Whichever trips
first refuses the request.

The REST endpoints share those tallies rather than keeping their own. An
attacker turned away at ``/login/`` gains nothing by moving to
``/api/auth/login/``, which is what two separate allowances on one account
would have given them.

With no ``REDIS_URL`` set the cache is per-process, so each gunicorn worker
keeps a separate tally and the real limit is the configured one times the
worker count. Render runs this on a single worker (see ``render.yaml``), and
pointing ``REDIS_URL`` at a shared instance makes the count exact across any
number of them.
"""

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.throttling import BaseThrottle


LOGIN = 'login'
REGISTER = 'register'
RESEND = 'resend'
PASSWORD_CHANGE = 'password-change'
MFA_CODE = 'mfa-code'

LIMITS = {
    LOGIN: (8, 900),
    REGISTER: (5, 3600),
    RESEND: (4, 3600),
    PASSWORD_CHANGE: (6, 900),
    MFA_CODE: (6, 900),
}


def client_address(request):
    """Best available address for the caller.

    Behind Render the socket address is the load balancer's, and the caller's
    is the leftmost entry of ``X-Forwarded-For``. That header is trusted only
    when ``TRUST_FORWARDED_FOR`` is on, because anyone can send it directly to
    a server that is not actually behind a proxy.

    A caller who forges the header still only escapes their own address
    counter. The per-account counter does not read the request at all, which is
    why both exist.
    """
    if getattr(settings, 'TRUST_FORWARDED_FOR', False):
        forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
        if forwarded:
            return forwarded.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip() or 'unknown'


def as_caller(address):
    """A stand-in request carrying one address, and nothing else.

    Work that outlives its request still has to be audited, and
    ``ActivityLog.record`` reads exactly one thing off a request: the caller's
    address. Passing the real request into a background thread would hand it an
    object whose files are already deleted and whose session is closed, so the
    address is copied out at the door and travels on its own.
    """
    from types import SimpleNamespace

    return SimpleNamespace(META={'REMOTE_ADDR': address or ''})


def _keys(scope, request, subject):
    """Cache keys for one attempt: one per address, one per named account."""
    keys = [f'throttle:{scope}:ip:{client_address(request)}']
    subject = (subject or '').strip().lower()
    if subject:
        keys.append(f'throttle:{scope}:id:{subject}')
    return keys


def retry_after(scope, request, subject=''):
    """Seconds the caller must wait, or ``None`` when the attempt may proceed.

    Reads the tally without touching it, so a caller who is already locked out
    does not extend their own lockout merely by knocking.
    """
    limit, window = LIMITS[scope]
    for key in _keys(scope, request, subject):
        if (cache.get(key) or 0) >= limit:
            ttl = _ttl(key)
            return ttl if ttl and ttl > 0 else window
    return None


def register_failure(scope, request, subject=''):
    """Count one failed attempt against both the address and the account."""
    _, window = LIMITS[scope]
    for key in _keys(scope, request, subject):
        try:
            cache.add(key, 0, window)
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, window)


def clear(scope, request, subject=''):
    """Forget the tally after a success, so one good sign-in resets the count."""
    cache.delete_many(_keys(scope, request, subject))


def _ttl(key):
    """Remaining lifetime of a cache key, when the backend can report one.

    Only the Redis backend exposes this. Everything else returns ``None`` and
    the caller falls back to quoting the whole window, which overstates the
    wait but never understates it.
    """
    try:
        return cache.ttl(key)
    except (AttributeError, NotImplementedError):
        return None


def wait_message(seconds, subject='attempts'):
    """Phrase a lockout for a person, rounded up to whole minutes."""
    minutes = max(1, -(-int(seconds) // 60))
    unit = 'minute' if minutes == 1 else 'minutes'
    return (f'Too many {subject}. For security, this has been paused. '
            f'Try again in about {minutes} {unit}.')


class CredentialThrottle(BaseThrottle):
    """Refuse an API credential request the shared tally has already locked out.

    Subclasses name a scope. The keys are the ones the web forms already write,
    so the two surfaces spend one allowance between them.

    A throttle only refuses; it never counts. Counting stays in the view, which
    is the only place that can tell a wrong password from a right one -- see
    :func:`register_failure` and :func:`clear`.
    """

    scope = ''
    subject_field = 'email'

    def subject(self, request):
        """The account named in the body, or ``''`` when it names none.

        A body that cannot be parsed still leaves the address counter, which is
        the half that does not need to know who is being tried.
        """
        try:
            data = request.data
        except (ParseError, UnsupportedMediaType):
            return ''
        if not hasattr(data, 'get'):
            return ''
        return str(data.get(self.subject_field) or '')

    def allow_request(self, request, view):
        """Read the tally without touching it."""
        self.waiting = retry_after(self.scope, request, self.subject(request))
        return self.waiting is None

    def wait(self):
        """Seconds until the caller may try again, for ``Retry-After``."""
        return self.waiting


class LoginThrottle(CredentialThrottle):
    """The sign-in allowance, shared with the ``/login/`` form."""

    scope = LOGIN


class RegisterThrottle(CredentialThrottle):
    """The registration allowance, shared with the ``/register/`` form."""

    scope = REGISTER
