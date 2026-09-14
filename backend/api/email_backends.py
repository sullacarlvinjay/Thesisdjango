import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

API_URL = 'https://api.brevo.com/v3/smtp/email'

CREATED = 201


class BrevoSendError(Exception):
    pass


def _address(value):
    name, email = parseaddr(value or '')
    entry = {'email': email or value or ''}
    if name:
        entry['name'] = name
    return entry


class BrevoEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, api_key=None, timeout=None, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = (getattr(settings, 'BREVO_API_KEY', '')
                        if api_key is None else api_key)
        self.timeout = (getattr(settings, 'EMAIL_TIMEOUT', 10)
                        if timeout is None else timeout)

    def send_messages(self, email_messages):
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
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception('Brevo refused a message to %s', message.to)
        return sent

    def _payload(self, message):
        recipients = [_address(a) for a in message.to if a]
        if not recipients:
            raise BrevoSendError('The message named no recipient.')

        payload = {
            'sender': _address(message.from_email or settings.DEFAULT_FROM_EMAIL),
            'to': recipients,
            'subject': message.subject or '',
        }
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
            for content, mimetype in getattr(message, 'alternatives', []) or []:
                if mimetype == 'text/html':
                    payload['htmlContent'] = content
                    break
        return payload

    def _send(self, message):
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
            detail = ''
            try:
                detail = exc.read().decode('utf-8', 'replace').strip()
            except Exception:
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
