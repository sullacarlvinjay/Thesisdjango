"""The one command that is allowed to be loud about mail.

Everything else in this system is deliberately quiet: ``notify.send_email``
catches and logs so a review screen cannot fail over SMTP, and settings.py falls
back to the console backend so a laptop and the test suite never touch a mail
server. Together those mean a misconfigured deployment is indistinguishable from
a working one — messages go to the service log, every caller is told 'sent', and
nobody is emailed.

So the property worth guarding here is the opposite of everywhere else: this
command must refuse to call a non-delivery a success, and must name the cause
when a send fails rather than swallowing it.
"""
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

SMTP = 'django.core.mail.backends.smtp.EmailBackend'
CONSOLE = 'django.core.mail.backends.console.EmailBackend'


class CheckEmailTest(TestCase):

    def run_it(self, to='someone@example.com'):
        from io import StringIO
        out = StringIO()
        call_command('check_email', to, stdout=out)
        return out.getvalue()

    # ── The failure this exists to catch ────────────────────────────────────

    @override_settings(EMAIL_BACKEND=CONSOLE, EMAIL_HOST='')
    def test_the_console_backend_is_reported_as_non_delivery(self):
        """It prints and discards. Calling that 'sent' is the whole problem."""
        with self.assertRaises(CommandError) as caught:
            self.run_it()
        message = str(caught.exception)
        self.assertIn('console backend', message)
        self.assertIn('nothing is delivered', message)
        # And says what to do about it, on the deployment where it matters.
        self.assertIn('EMAIL_HOST', message)
        self.assertIn('Render', message)

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST='')
    def test_an_smtp_backend_with_no_host_is_refused_too(self):
        """The backend can be set while the host it needs is not."""
        with self.assertRaises(CommandError):
            self.run_it()

    # ── Failures are explained, not swallowed ───────────────────────────────

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST='smtp.gmail.com')
    def test_a_refused_login_names_the_app_password(self):
        """Gmail's own error says 'BadCredentials' and nothing more useful."""
        from smtplib import SMTPAuthenticationError

        with mock.patch('api.management.commands.check_email.get_connection') as conn:
            conn.return_value.open.side_effect = SMTPAuthenticationError(
                535, b'5.7.8 Username and Password not accepted')
            with self.assertRaises(CommandError) as caught:
                self.run_it()

        message = str(caught.exception)
        self.assertIn('SMTPAuthenticationError', message)
        self.assertIn('App Password', message)

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST='smtp.typo.invalid')
    def test_a_host_that_does_not_resolve_says_so(self):
        with mock.patch('api.management.commands.check_email.get_connection') as conn:
            conn.return_value.open.side_effect = OSError('getaddrinfo failed')
            with self.assertRaises(CommandError) as caught:
                self.run_it()
        self.assertIn('Could not connect', str(caught.exception))

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST='smtp.example.com')
    def test_a_refused_message_is_reported_rather_than_counted_as_sent(self):
        from smtplib import SMTPSenderRefused

        with mock.patch('api.management.commands.check_email.get_connection'), \
             mock.patch('api.management.commands.check_email.send_mail') as send:
            send.side_effect = SMTPSenderRefused(
                553, b'From address not owned', 'no-reply@bipsu.edu.ph')
            with self.assertRaises(CommandError) as caught:
                self.run_it()

        message = str(caught.exception)
        self.assertIn('refused the message', message)
        self.assertIn('DEFAULT_FROM_EMAIL', message)

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST='smtp.example.com')
    def test_a_backend_reporting_zero_sends_is_not_a_success(self):
        with mock.patch('api.management.commands.check_email.get_connection'), \
             mock.patch('api.management.commands.check_email.send_mail', return_value=0):
            with self.assertRaises(CommandError) as caught:
                self.run_it()
        self.assertIn('no message was sent', str(caught.exception))

    # ── The success path ────────────────────────────────────────────────────

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST='smtp.example.com',
                       EMAIL_HOST_USER='srms@bipsu.edu.ph',
                       SITE_URL='https://srms.bipsu.edu.ph')
    def test_a_send_that_works_says_accepted_not_delivered(self):
        """A server accepting a message is not the same as anyone receiving it."""
        with mock.patch('api.management.commands.check_email.get_connection'), \
             mock.patch('api.management.commands.check_email.send_mail', return_value=1):
            out = self.run_it('juan@gmail.com')

        self.assertIn('accepted for delivery to juan@gmail.com', out)
        self.assertIn('not the same as it arriving', out)
        self.assertIn('spam folder', out)

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST='smtp.example.com', SITE_URL='')
    def test_a_missing_site_url_is_warned_about_on_success(self):
        with mock.patch('api.management.commands.check_email.get_connection'), \
             mock.patch('api.management.commands.check_email.send_mail', return_value=1):
            out = self.run_it()
        self.assertIn('SITE_URL is unset', out)

    # ── What it prints about itself ─────────────────────────────────────────

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST='smtp.example.com',
                       EMAIL_HOST_PASSWORD='hunter2-app-password')
    def test_the_password_is_never_printed(self):
        """This runs in a shell whose scrollback is shared and often pasted."""
        with mock.patch('api.management.commands.check_email.get_connection'), \
             mock.patch('api.management.commands.check_email.send_mail', return_value=1):
            out = self.run_it()

        self.assertNotIn('hunter2-app-password', out)
        self.assertIn('EMAIL_HOST_PASSWORD', out)
        self.assertIn('set', out)


class DefaultFromEmailTest(TestCase):
    """Who the From line says the message is from.

    Derived from the account being logged into unless something is set
    explicitly, because a mail server will not honour a From address the sending
    account does not own: Gmail rewrites it to the authenticated account and
    delivers under that. A DEFAULT_FROM_EMAIL of no-reply@bipsu.edu.ph on a
    Gmail login therefore reads as a lie — recipients see the Gmail address.
    """

    def from_email(self, **env):
        import importlib
        import os

        import config.settings

        keys = ('EMAIL_HOST', 'EMAIL_HOST_USER', 'DEFAULT_FROM_EMAIL')
        saved = {k: os.environ.get(k) for k in keys}
        try:
            for k in keys:
                os.environ.pop(k, None)
            os.environ.update(env)
            return importlib.reload(config.settings).DEFAULT_FROM_EMAIL
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v
            importlib.reload(config.settings)

    def test_it_is_derived_from_the_account_that_sends(self):
        self.assertEqual(
            self.from_email(EMAIL_HOST='smtp.gmail.com',
                            EMAIL_HOST_USER='bipsu.srms@gmail.com'),
            'BiPSU SRMS <bipsu.srms@gmail.com>')

    def test_an_explicit_address_still_wins(self):
        """For an institutional mailbox, or a verified 'Send mail as' alias."""
        self.assertEqual(
            self.from_email(EMAIL_HOST='smtp.bipsu.edu.ph',
                            EMAIL_HOST_USER='srms@bipsu.edu.ph',
                            DEFAULT_FROM_EMAIL='BiPSU SRMS <no-reply@bipsu.edu.ph>'),
            'BiPSU SRMS <no-reply@bipsu.edu.ph>')

    def test_a_blank_override_falls_back_rather_than_sending_from_nobody(self):
        """An env var set to whitespace is unset, not an empty From line."""
        self.assertEqual(
            self.from_email(EMAIL_HOST='smtp.gmail.com',
                            EMAIL_HOST_USER='bipsu.srms@gmail.com',
                            DEFAULT_FROM_EMAIL='   '),
            'BiPSU SRMS <bipsu.srms@gmail.com>')

    def test_with_no_mail_configured_it_is_still_a_valid_address(self):
        """The console backend prints it; it must not read as 'BiPSU SRMS <>'."""
        self.assertEqual(self.from_email(),
                         'BiPSU SRMS <no-reply@bipsu.edu.ph>')


class DeployCheckTest(TestCase):
    """The warning that finds you, rather than waiting to be looked for.

    api/checks.py exists because settings.py can only see whether EMAIL_HOST is
    set, and the console backend it falls back to reports success for every
    message it discards. On a laptop that is right; on a deployment it means
    nobody has been emailed and nothing said so.
    """

    def run_check(self):
        from api.checks import email_is_configured_in_production
        return email_is_configured_in_production(None)

    @override_settings(DEBUG=False, EMAIL_HOST='', EMAIL_BACKEND=CONSOLE)
    def test_a_deployment_with_no_mail_host_is_warned_about(self):
        issues = self.run_check()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, 'api.W001')
        self.assertIn('no email will be sent', issues[0].msg)
        self.assertIn('Render dashboard', issues[0].hint)
        self.assertIn('check_email', issues[0].hint)

    @override_settings(DEBUG=False, EMAIL_HOST='smtp.gmail.com')
    def test_a_configured_deployment_is_silent(self):
        self.assertEqual(self.run_check(), [])

    @override_settings(DEBUG=True, EMAIL_HOST='')
    def test_a_laptop_is_silent(self):
        """The console backend is the correct setting there, not a mistake."""
        self.assertEqual(self.run_check(), [])

    @override_settings(DEBUG=False, EMAIL_HOST='',
                       EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_a_test_run_is_silent(self):
        """Django's runner forces DEBUG=False and swaps in locmem.

        Without this the warning printed on every single `manage.py test`, and
        one that cries wolf that often is one nobody reads on the day it counts.
        """
        self.assertEqual(self.run_check(), [])

    @override_settings(DEBUG=False, EMAIL_HOST='', EMAIL_BACKEND=CONSOLE)
    def test_it_is_a_warning_and_never_an_error(self):
        """A deploy must not fail over mail: the site works without it."""
        from django.core.checks import Error

        issue = self.run_check()[0]
        self.assertNotIsInstance(issue, Error)
        self.assertFalse(issue.is_serious())

    def test_it_is_registered_so_manage_py_runs_it(self):
        """Unregistered it would be dead code that never once fired."""
        from django.core.checks import registry

        self.assertIn(
            'email_is_configured_in_production',
            [c.__name__ for c in registry.registry.get_checks()])
