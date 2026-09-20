"""Confirming that a registrant's email address is real.

The address is signed into the token along with the account ID, so a link stops
working once the address changes. Confirming does not sign anyone in — the
office still reviews every registration — it establishes only that the address
is reachable, which is how the applicant will be told the decision.
"""

import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.core.validators import validate_email

logger = logging.getLogger(__name__)

SALT = 'api.email_verify.confirm'

CONFIRM_MAX_AGE = 3 * 24 * 60 * 60

_DOMAIN = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?'
                     r'(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*'
                     r'\.[A-Za-z]{2,}$')


def address_error(email):
    """Why this address cannot be written to, or '' if it can.

    Checked beyond Django's own validator because the address is the only
    way the office reaches an applicant. A typo here does not surface as
    an error later; it surfaces as a scholar who was never told anything.
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
    """A signed, expiring token identifying the user and their address.

    The address is signed into the token as well as the ID, so a link
    stops working once the address changes — see :func:`read_token`.
    """
    return TimestampSigner(salt=SALT).sign(f'{user.pk}:{user.email}')


def read_token(token, max_age=None):
    """Read a confirmation token back to the user who was sent it.

    Returns:
        ``(user, '')`` when the link is good, otherwise ``(None, reason)``
        where reason is ``'expired'``, ``'invalid'`` or ``'stale'``.
        ``'stale'`` means the address changed after the link was sent, so
        confirming it would confirm an address nobody now holds.
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
    if (user.email or '').lower() != email.lower():
        return None, 'stale'
    return user, ''


def confirmation_url(user, request=None):
    """The absolute link to put in the confirmation email.

    Falls back to the request's host when ``SITE_URL`` is unset, and to a
    bare path when there is no request either — a relative link is useless
    in an inbox, but it is better than a link to the wrong host.
    """
    path = f'/register/verify/{make_token(user)}/'
    base = getattr(settings, 'SITE_URL', '')
    if base:
        return f'{base}{path}'
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def send_confirmation(user, request=None):
    """Email the address-confirmation link and record the attempt.

    The timestamp is written whether or not the send succeeded, because it
    is what rate-limits the resend button.

    The message is queued rather than sent, so nothing is returned: making a
    registrant wait out a mail round trip before their own page loads bought
    them an answer none of the callers read.
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
    notify.queue_email(
        user.email, '[BiPSU SRMS] Confirm your email address', body)

    user.email_confirmation_sent_at = timezone.now()
    user.save(update_fields=['email_confirmation_sent_at'])
