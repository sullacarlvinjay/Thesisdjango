"""Sending over HTTPS, because Render's free plan blocks SMTP.

The bug behind this file was invisible from inside the application. Render
stopped allowing outbound traffic to ports 25, 465 and 587 from free web
services, so every send timed out and `api.notify.send_email` swallowed it —
which is what that function is for. Nothing was misconfigured and nothing was
logged as a failure the office would see; the site simply stopped emailing
anyone.

What is pinned here is the shape of the request, because that is the part no
test elsewhere touches and the part a provider refuses silently: the sender, the
recipient, the plain-text body. Also that a refusal *raises* rather than
returning success, since a backend that reports a refused message as sent would
reproduce the original bug exactly, over a different transport.

Nothing here reaches the network. urlopen is replaced; what is checked is what
would have been sent.
"""
import json
from unittest import mock

from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail
from django.test import SimpleTestCase, override_settings

from api.email_backends import BrevoEmailBackend, BrevoSendError

BACKEND = 'api.email_backends.BrevoEmailBackend'


class _Response:
    """The bare minimum of what urlopen's context manager yields."""

    def __init__(self, status=201):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def sent_payload(mock_urlopen):
    """The JSON body of the one request that was made."""
    request = mock_urlopen.call_args[0][0]
    return json.loads(request.data.decode('utf-8'))


@override_settings(EMAIL_BACKEND=BACKEND, BREVO_API_KEY='test-key',
                   DEFAULT_FROM_EMAIL='BiPSU SRMS <sdso@bipsu.edu.ph>')
class TheRequestBrevoReceivesTest(SimpleTestCase):
    def send(self, **kwargs):
        with mock.patch('urllib.request.urlopen',
                        return_value=_Response()) as urlopen:
            count = send_mail(
                subject=kwargs.pop('subject', 'Confirm your email address'),
                message=kwargs.pop('message', 'Open the link.'),
                from_email=kwargs.pop('from_email', None),
                recipient_list=kwargs.pop('recipient_list', ['ana@bipsu.edu.ph']),
                **kwargs)
        return count, urlopen

    def test_a_message_is_posted_to_the_transactional_endpoint(self):
        count, urlopen = self.send()
        self.assertEqual(count, 1)
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(request.method, 'POST')

    def test_the_api_key_travels_in_the_header_brevo_reads(self):
        """Not Authorization: Brevo reads a header of its own name."""
        _count, urlopen = self.send()
        headers = urlopen.call_args[0][0].headers
        # urllib title-cases header names.
        self.assertEqual(headers.get('Api-key'), 'test-key')

    def test_the_recipient_and_subject_are_carried(self):
        _count, urlopen = self.send()
        payload = sent_payload(urlopen)
        self.assertEqual(payload['to'], [{'email': 'ana@bipsu.edu.ph'}])
        self.assertEqual(payload['subject'], 'Confirm your email address')

    def test_a_plain_text_body_is_sent_as_text_not_html(self):
        """Every message this system sends is plain text."""
        _count, urlopen = self.send(message='Open the link.')
        payload = sent_payload(urlopen)
        self.assertEqual(payload['textContent'], 'Open the link.')
        self.assertNotIn('htmlContent', payload)

    def test_a_display_name_on_the_sender_is_split_out(self):
        """'BiPSU SRMS <a@b>' is two fields to Brevo, not one string."""
        _count, urlopen = self.send()
        self.assertEqual(sent_payload(urlopen)['sender'],
                         {'email': 'sdso@bipsu.edu.ph', 'name': 'BiPSU SRMS'})

    def test_a_bare_sender_address_carries_no_name(self):
        _count, urlopen = self.send(from_email='sdso@bipsu.edu.ph')
        self.assertEqual(sent_payload(urlopen)['sender'],
                         {'email': 'sdso@bipsu.edu.ph'})

    def test_the_default_from_address_is_used_when_none_is_given(self):
        """notify.send_email passes DEFAULT_FROM_EMAIL; this is that path."""
        _count, urlopen = self.send(from_email=None)
        self.assertEqual(sent_payload(urlopen)['sender']['email'],
                         'sdso@bipsu.edu.ph')

    def test_an_html_alternative_is_carried_alongside_the_text(self):
        """Unused today. A message that arrived blank would be a silent bug."""
        message = EmailMultiAlternatives(
            'Subject', 'plain', 'a@b.ph', ['ana@bipsu.edu.ph'])
        message.attach_alternative('<p>rich</p>', 'text/html')
        with mock.patch('urllib.request.urlopen',
                        return_value=_Response()) as urlopen:
            message.send()
        payload = sent_payload(urlopen)
        self.assertEqual(payload['textContent'], 'plain')
        self.assertEqual(payload['htmlContent'], '<p>rich</p>')

    def test_bcc_is_carried_rather_than_dropped(self):
        message = EmailMessage('Subject', 'body', 'a@b.ph', ['ana@bipsu.edu.ph'],
                               bcc=['office@bipsu.edu.ph'])
        with mock.patch('urllib.request.urlopen',
                        return_value=_Response()) as urlopen:
            message.send()
        self.assertEqual(sent_payload(urlopen)['bcc'],
                         [{'email': 'office@bipsu.edu.ph'}])

    def test_one_request_per_message_so_addresses_do_not_leak(self):
        """Batching would put one applicant's address in another's headers."""
        messages = [
            EmailMessage('S', 'b', 'a@b.ph', ['one@bipsu.edu.ph']),
            EmailMessage('S', 'b', 'a@b.ph', ['two@bipsu.edu.ph']),
        ]
        with mock.patch('urllib.request.urlopen',
                        return_value=_Response()) as urlopen:
            sent = BrevoEmailBackend().send_messages(messages)
        self.assertEqual(sent, 2)
        self.assertEqual(urlopen.call_count, 2)


@override_settings(EMAIL_BACKEND=BACKEND, BREVO_API_KEY='test-key',
                   DEFAULT_FROM_EMAIL='BiPSU SRMS <sdso@bipsu.edu.ph>')
class ARefusalIsNotSuccessTest(SimpleTestCase):
    """The whole point. A refusal reported as sent is the original bug again."""

    def _refuse(self, code=400, body=b'{"message":"sender not valid"}'):
        import urllib.error
        return urllib.error.HTTPError(
            'https://api.brevo.com/v3/smtp/email', code, 'Bad Request', {},
            __import__('io').BytesIO(body))

    def test_a_refusal_raises_rather_than_reporting_a_send(self):
        message = EmailMessage('S', 'b', 'a@b.ph', ['ana@bipsu.edu.ph'])
        with mock.patch('urllib.request.urlopen', side_effect=self._refuse()):
            with self.assertRaises(BrevoSendError):
                BrevoEmailBackend().send_messages([message])

    def test_the_reason_brevo_gave_is_carried_into_the_error(self):
        """'sender not valid' and 'key not found' are both a 4xx otherwise."""
        message = EmailMessage('S', 'b', 'a@b.ph', ['ana@bipsu.edu.ph'])
        with mock.patch('urllib.request.urlopen', side_effect=self._refuse()):
            with self.assertRaises(BrevoSendError) as caught:
                BrevoEmailBackend().send_messages([message])
        self.assertIn('sender not valid', str(caught.exception))

    def test_fail_silently_counts_the_refusal_as_unsent(self):
        """api.notify catches everything; it must not be told 1 was sent."""
        message = EmailMessage('S', 'b', 'a@b.ph', ['ana@bipsu.edu.ph'])
        with mock.patch('urllib.request.urlopen', side_effect=self._refuse()):
            sent = BrevoEmailBackend(fail_silently=True).send_messages([message])
        self.assertEqual(sent, 0)

    def test_notify_reports_a_refusal_as_not_emailed(self):
        """The office is shown this; it must not read as delivered."""
        from api import notify
        with mock.patch('urllib.request.urlopen', side_effect=self._refuse()):
            self.assertFalse(
                notify.send_email('ana@bipsu.edu.ph', 'Subject', 'Body'))

    def test_a_missing_api_key_is_refused_rather_than_silently_dropped(self):
        """And refused here, before any request is made.

        urlopen is mocked to prove it: an empty key that fell through to the
        configured one would send a real message from a test meant to check the
        refusal, which is how this was caught.
        """
        message = EmailMessage('S', 'b', 'a@b.ph', ['ana@bipsu.edu.ph'])
        with mock.patch('urllib.request.urlopen') as urlopen:
            with self.assertRaises(BrevoSendError) as caught:
                BrevoEmailBackend(api_key='').send_messages([message])
        self.assertIn('BREVO_API_KEY', str(caught.exception))
        urlopen.assert_not_called()

    def test_an_unreachable_api_says_it_is_not_a_blocked_port(self):
        """The distinction that cost a week the first time round."""
        import urllib.error
        message = EmailMessage('S', 'b', 'a@b.ph', ['ana@bipsu.edu.ph'])
        with mock.patch('urllib.request.urlopen',
                        side_effect=urllib.error.URLError('unreachable')):
            with self.assertRaises(BrevoSendError) as caught:
                BrevoEmailBackend().send_messages([message])
        self.assertIn('443', str(caught.exception))


class RouteSelectionTest(SimpleTestCase):
    """Which backend settings.py picks, and what EMAIL_ENABLED then means."""

    def _reload(self, **env):
        """Re-evaluate the email block of settings.py under a given environment."""
        import importlib
        import os
        from django.conf import settings as django_settings

        keys = ('BREVO_API_KEY', 'EMAIL_HOST', 'EMAIL_HOST_USER')
        with mock.patch.dict(os.environ,
                             {k: env.get(k, '') for k in keys}, clear=False):
            module = importlib.import_module(django_settings.SETTINGS_MODULE)
            importlib.reload(module)
            return module

    def test_brevo_wins_when_both_routes_are_configured(self):
        """Left-over SMTP must not quietly outrank the route someone turned on."""
        module = self._reload(BREVO_API_KEY='k', EMAIL_HOST='smtp.gmail.com')
        self.assertEqual(module.EMAIL_BACKEND, BACKEND)
        self.assertTrue(module.EMAIL_ENABLED)

    def test_smtp_is_used_when_no_api_key_is_set(self):
        module = self._reload(EMAIL_HOST='smtp.gmail.com')
        self.assertEqual(module.EMAIL_BACKEND,
                         'django.core.mail.backends.smtp.EmailBackend')
        self.assertTrue(module.EMAIL_ENABLED)

    def test_neither_falls_back_to_the_console_and_says_mail_is_off(self):
        module = self._reload()
        self.assertEqual(module.EMAIL_BACKEND,
                         'django.core.mail.backends.console.EmailBackend')
        self.assertFalse(module.EMAIL_ENABLED)

    def test_the_sender_address_is_read_on_the_brevo_route_too(self):
        """Brevo refuses any sender but the verified one, so it must survive."""
        module = self._reload(BREVO_API_KEY='k', EMAIL_HOST_USER='sdso@bipsu.edu.ph')
        self.assertEqual(module.EMAIL_HOST_USER, 'sdso@bipsu.edu.ph')
        self.assertIn('sdso@bipsu.edu.ph', module.DEFAULT_FROM_EMAIL)
