"""Proving that the address someone registered with is real, and theirs.

The registration form used to take any address at all. Nothing checked that it
was well formed, that its domain existed, or — the part that actually matters —
that the person filling in the form could read mail at it. A student who
mistyped their address got an account nobody could ever reach, and an address
belonging to somebody else got one too. Every message the system sends after
that, the SDSO's own decision included, went to a stranger or to nowhere.

Two checks, in the order they can be made:

* :func:`address_error` runs on the posted form. It rejects what cannot be an
  address at all — no ``@``, no domain, a domain with no dot. Cheap, immediate,
  and it catches the fat-finger cases before an account exists.

* the confirmation link proves the rest. There is no test for 'is this address
  real' that beats sending something to it and seeing whether anyone opens it,
  and that same act proves the person registering can read mail there.

**Deliberately not done here: a DNS or MX lookup.** It reads like the stronger
check and is not. A domain that serves mail through MX records alone resolves
no A record, a nameserver that is slow or briefly down looks exactly like a
domain that does not exist, and either one turns into a real student being
refused registration for an address that works. The confirmation link answers
the same question without the false rejections.

The token carries no database row. ``TimestampSigner`` signs the account id and
the address together, so a link expires on its own, cannot be forged without
the SECRET_KEY, and stops working the moment the address on the account changes
— a link mailed to the old address must not confirm the new one.

Confirmation is not a sign-in gate. Mail is optional in this deployment (see
``settings.EMAIL_ENABLED``), so making it one would lock every applicant out of
an installation with no SMTP configured. It is a fact the SDSO is shown while
deciding: an unconfirmed address is one nobody has been able to reach.
"""
import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.core.validators import validate_email

logger = logging.getLogger(__name__)

SALT = 'api.email_verify.confirm'

# Three days, matching middleware.AUTO_RELEASE_WINDOW — the same span the
# registration is expected to be resolved in.
CONFIRM_MAX_AGE = 3 * 24 * 60 * 60

# Django's validator already refuses a dotless or malformed domain. What it
# lets through on purpose, and this closes, is the two forms that are valid mail
# addresses but never a real one on a public registration form: 'localhost',
# which it keeps on an allowlist, and an IP literal such as 'juan@[127.0.0.1]'.
# A domain has at least one dot and ends in letters.
_DOMAIN = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?'
                     r'(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*'
                     r'\.[A-Za-z]{2,}$')


def address_error(email):
    """'' when the address could be real, otherwise what is wrong with it.

    The wording is what the registrant reads on the form, so it says what to do
    rather than naming a rule.
    """
    email = (email or '').strip()
    if not email:
        return 'Enter your email address — it is how the office reaches you.'
    if len(email) > 254:
        return 'That email address is too long to be real. Check it for a typo.'
    try:
        validate_email(email)
    except ValidationError:
        return (f'{email} is not a valid email address. Check it for a typo — '
                'the office writes to this address about your application.')
    domain = email.rsplit('@', 1)[1]
    if not _DOMAIN.match(domain):
        return (f'{domain} is not a domain that can receive mail. Use an address '
                'you can actually open, such as your Gmail or your BiPSU one.')
    return ''


def make_token(user):
    """A signed link token for this account and the address it holds now."""
    return TimestampSigner(salt=SALT).sign(f'{user.pk}:{user.email}')


def read_token(token, max_age=None):
    """The account a token names, or ``(None, reason)`` if it does not name one.

    Returns ``(user, '')`` on success. The reason is what the page tells the
    visitor, so an expired link and a forged one are told apart — one of those
    is an ordinary thing to happen to a person and the other is not.

    ``max_age`` is read from the module at call time rather than bound as a
    default, so the window is one value a caller or a test can move.
    """
    from .models import User

    if max_age is None:
        max_age = CONFIRM_MAX_AGE
    try:
        raw = TimestampSigner(salt=SALT).unsign(token, max_age=max_age)
    except SignatureExpired:
        return None, 'expired'
    except (BadSignature, TypeError):
        return None, 'invalid'

    pk, _, email = raw.partition(':')
    user = User.objects.filter(pk=pk).first()
    if user is None:
        return None, 'invalid'
    # The address changed after the link was sent. Confirming would prove
    # somebody could read the old one, which says nothing about the new.
    if (user.email or '').lower() != email.lower():
        return None, 'stale'
    return user, ''


def confirmation_url(user, request=None):
    """The link to put in the email, absolute wherever that is possible.

    A relative path in an email is not a link at all — nobody can click it — so
    three sources in order of authority:

    1. ``SITE_URL``, which is the only one that survives a proxy rewriting the
       host, and the only one right when mail is sent outside a request;
    2. the request itself, so an installation that never set SITE_URL still
       sends something clickable. ``ALLOWED_HOSTS`` already rejects a request
       whose Host header is not ours, so this cannot be pointed elsewhere;
    3. the bare path, which is what the console backend prints in development.
    """
    path = f'/register/verify/{make_token(user)}/'
    base = getattr(settings, 'SITE_URL', '')
    if base:
        return f'{base}{path}'
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def send_confirmation(user, request=None):
    """Email the confirmation link and stamp when it went. Returns True if sent.

    Best-effort in the same way :mod:`api.notify` is: a registration that has
    already been saved must not be lost because SMTP was down. The stamp is
    written either way, because it records that we asked — the SDSO page reads
    it to say 'waiting on them' rather than 'never asked'.
    """
    from django.utils import timezone
    from . import notify

    link = confirmation_url(user, request)
    name = user.first_name or 'there'
    body = (
        f'Hi {name},\n\n'
        'Someone registered for the BiPSU Scholarship Records Management System '
        f'with this address. Open the link below to confirm it is yours:\n\n'
        f'{link}\n\n'
        'The link works for three days. Confirming does not sign you in — the '
        'SDSO office still reviews every registration — but it is how we know '
        'we can reach you with their decision.\n\n'
        'If you did not register, you can ignore this message. Nothing happens '
        'until the link is opened.'
    )
    sent = notify.send_email(
        user.email, '[BiPSU SRMS] Confirm your email address', body)

    user.email_confirmation_sent_at = timezone.now()
    user.save(update_fields=['email_confirmation_sent_at'])
    return sent
