"""Sending mail over HTTPS, because Render's free plan blocks SMTP.

Render stopped allowing outbound traffic to ports 25, 465 and 587 from free web
services in September 2025. Nothing about the SMTP configuration was wrong —
the connection simply never left the container, and every send timed out after
``EMAIL_TIMEOUT`` seconds and was swallowed by :func:`api.notify.send_email`,
which is exactly what that function is built to do. The result was a site that
looked like it was emailing people and was not.

An HTTP email API goes out over 443 like any other request, so it is unaffected.
This is a Django email backend rather than a call bolted onto ``notify``: every
sender in this system goes through ``django.core.mail``, and swapping the
backend underneath means not one of them has to know which route is live. The
test suite's locmem backend keeps working for the same reason.

**Brevo, and why.** The choice turned on one thing — sending to student
addresses without owning a domain. Resend and most others verify a *domain* by
DNS record, and nobody here can add records to bipsu.edu.ph. Brevo verifies a
single *sender address* by emailing it a link, which an office Gmail can do in a
minute. Its free tier is 300 messages a day, well beyond what a registration
confirmation and a decision notice add up to.

The sender must be that verified address. ``DEFAULT_FROM_EMAIL`` is derived from
``EMAIL_HOST_USER`` (see settings.py), so setting the two to the address you
verified is all that is needed; Brevo refuses anything else, and says so.
"""
import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

API_URL = 'https://api.brevo.com/v3/smtp/email'

# Brevo answers 201 with a messageId. Anything else is a refusal worth reading:
# its body names the cause — an unverified sender, a bad key, the daily cap —
# far better than the status code does.
CREATED = 201


class BrevoSendError(Exception):
    """A message Brevo refused, with what it said about it.

    Carries the response body rather than only the status, because that body is
    the whole diagnosis: 'sender not valid' and 'key not found' are the same 401
    otherwise, and they are fixed in completely different places.
    """


def _address(value):
    """{'email': ..., 'name': ...} from 'BiPSU SRMS <a@b.c>' or 'a@b.c'."""
    name, email = parseaddr(value or '')
    entry = {'email': email or value or ''}
    if name:
        entry['name'] = name
    return entry


class BrevoEmailBackend(BaseEmailBackend):
    """Django email backend that posts to Brevo's transactional API.

    Stdlib ``urllib`` rather than ``requests``: this is one POST of a small JSON
    body, and the free plan's 512 MB is already accounted for elsewhere. One
    dependency not added is one not to keep pinned.
    """

    def __init__(self, fail_silently=False, api_key=None, timeout=None, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        # `None` means 'not specified, read the setting'; an empty string means
        # 'explicitly none'. Falling back on falsiness would quietly reinstate
        # the configured key for a caller that deliberately passed no key, and
        # send a real message from a test that meant to check the refusal.
        self.api_key = (getattr(settings, 'BREVO_API_KEY', '')
                        if api_key is None else api_key)
        self.timeout = (getattr(settings, 'EMAIL_TIMEOUT', 10)
                        if timeout is None else timeout)

    def send_messages(self, email_messages):
        """Send each message; return how many Brevo accepted.

        One request per message. Brevo can take several recipients in a single
        call, but every message this system sends goes to one person, and
        batching would put one applicant's address in another's headers.
        """
        if not email_messages:
            return 0
        if not self.api_key:
            if self.fail_silently:
                return 0
            raise BrevoSendError(
                'BREVO_API_KEY is not set, so no message can be sent. Create a '
                'key under Brevo > SMTP & API > API keys.')

        sent = 0
        for message in email_messages:
            try:
                self._send(message)
                sent += 1
            except Exception:                               # noqa: BLE001
                if not self.fail_silently:
                    raise
                logger.exception('Brevo refused a message to %s', message.to)
        return sent

    def _payload(self, message):
        """The JSON body for one EmailMessage."""
        recipients = [_address(a) for a in message.to if a]
        if not recipients:
            raise BrevoSendError('The message named no recipient.')

        payload = {
            'sender': _address(message.from_email or settings.DEFAULT_FROM_EMAIL),
            'to': recipients,
            'subject': message.subject or '',
        }
        # cc and bcc are unused by this system today, but dropping one silently
        # is the kind of bug nobody finds until it matters.
        if message.cc:
            payload['cc'] = [_address(a) for a in message.cc]
        if message.bcc:
            payload['bcc'] = [_address(a) for a in message.bcc]
        if getattr(message, 'reply_to', None):
            payload['replyTo'] = _address(message.reply_to[0])

        body = message.body or ''
        if getattr(message, 'content_subtype', 'plain') == 'html':
            payload['htmlContent'] = body
        else:
            payload['textContent'] = body
            # An HTML alternative, when a caller attached one. Every message in
            # this system is plain text; this costs three lines and means an
            # HTML one would not arrive blank.
            for content, mimetype in getattr(message, 'alternatives', []) or []:
                if mimetype == 'text/html':
                    payload['htmlContent'] = content
                    break
        return payload

    def _send(self, message):
        """POST one message. Raises :class:`BrevoSendError` on anything but 201."""
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(self._payload(message)).encode('utf-8'),
            headers={
                'api-key': self.api_key,
                'content-type': 'application/json',
                'accept': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status != CREATED:
                    raise BrevoSendError(
                        f'Brevo answered {response.status} rather than {CREATED}.')
        except urllib.error.HTTPError as exc:
            # The body is the diagnosis. Read it before the connection closes.
            detail = ''
            try:
                detail = exc.read().decode('utf-8', 'replace').strip()
            except Exception:                               # noqa: BLE001
                pass
            raise BrevoSendError(
                f'Brevo refused the message ({exc.code} {exc.reason}). {detail}'
            ) from exc
        except urllib.error.URLError as exc:
            raise BrevoSendError(
                f'Could not reach {API_URL}: {exc.reason}. Unlike SMTP this is '
                'ordinary HTTPS on port 443, so a failure here is the network '
                'or the API being down rather than a blocked port.'
            ) from exc
