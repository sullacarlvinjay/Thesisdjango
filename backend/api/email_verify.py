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
    return TimestampSigner(salt=SALT).sign(f'{user.pk}:{user.email}')


def read_token(token, max_age=None):
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
    path = f'/register/verify/{make_token(user)}/'
    base = getattr(settings, 'SITE_URL', '')
    if base:
        return f'{base}{path}'
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def send_confirmation(user, request=None):
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
