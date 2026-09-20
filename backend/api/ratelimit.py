"""Fixed-window throttling for the endpoints that accept credentials.

Tallies live in the ordinary Django cache rather than in a table. A throttle
that wrote a row per attempt would hand an attacker a cheap way to grow the
database, which is the opposite of what it is for.

Every credential endpoint is counted twice: once against the caller's address
and once against the account being named. The address counter slows a single
machine working through many accounts; the account counter slows a botnet
working through one account, which no address counter can see. Whichever trips
first refuses the request.

With no ``REDIS_URL`` set the cache is per-process, so each gunicorn worker
keeps a separate tally and the real limit is the configured one times the
worker count. Render runs this on a single worker (see ``render.yaml``), and
pointing ``REDIS_URL`` at a shared instance makes the count exact across any
number of them.
"""

from django.conf import settings
from django.core.cache import cache


LOGIN = 'login'
REGISTER = 'register'
RESEND = 'resend'
PASSWORD_CHANGE = 'password-change'

LIMITS = {
    LOGIN: (8, 900),
    REGISTER: (5, 3600),
    RESEND: (4, 3600),
    PASSWORD_CHANGE: (6, 900),
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
