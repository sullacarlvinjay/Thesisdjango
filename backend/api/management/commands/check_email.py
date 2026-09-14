from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management.base import BaseCommand, CommandError

CONSOLE = 'django.core.mail.backends.console.EmailBackend'
BREVO = 'api.email_backends.BrevoEmailBackend'

HINTS = [
    ('SMTPAuthenticationError',
     'The username or password was refused. For Gmail this is almost always the '
     'account password being used where an App Password is required: turn on '
     '2-Step Verification, then create one at myaccount.google.com > Security > '
     'App passwords and put that in EMAIL_HOST_PASSWORD.'),
    ('SMTPSenderRefused',
     'The server refused the From address. DEFAULT_FROM_EMAIL has to be an '
     'address that account is allowed to send as — Gmail rewrites or rejects '
     'anything that is not the account itself or a verified alias.'),
    ('SMTPRecipientsRefused',
     'The server accepted the login but refused the recipient. Check the '
     'address for a typo.'),
    ('SMTPNotSupportedError',
     'The server does not offer what was asked of it — usually EMAIL_USE_TLS '
     'and EMAIL_USE_SSL both set, or set the wrong way round for this port. '
     'Use TLS on 587, SSL on 465, never both.'),
    ('SMTPServerDisconnected',
     'The connection dropped mid-conversation. Often the wrong port for the '
     'encryption setting.'),
    ('SMTPConnectError',
     'Could not open a connection. The host or port is wrong, or outbound SMTP '
     'is blocked from this network — some hosting platforms block it and expect '
     'an email API instead of raw SMTP.'),
    ('BrevoSendError',
     'Brevo refused the message, and its own answer is quoted above. Two '
     'causes cover nearly all of them: the sender address is not one you '
     'have verified — verify it under Brevo > Senders, domains & '
     'dedicated IPs and make EMAIL_HOST_USER that same address — or '
     'the API key is wrong, revoked, or from a different account.'),
    ('gaierror',
     'The mail host name did not resolve. Check EMAIL_HOST for a typo.'),
    ('timeout',
     'The mail server did not answer within EMAIL_TIMEOUT seconds. Usually the '
     'port being blocked rather than the server being slow.'),
]


class Command(BaseCommand):
    help = 'Send one real email and report exactly what happened.'

    def add_arguments(self, parser):
        parser.add_argument('to', help='Address to send the test message to.')

    def handle(self, *args, **options):
        to = options['to'].strip()
        backend = getattr(settings, 'EMAIL_BACKEND', '')
        host = getattr(settings, 'EMAIL_HOST', '')
        over_http = backend == BREVO

        self.stdout.write('Configuration this send will use:')
        rows = [('EMAIL_BACKEND', backend)]
        if over_http:
            rows += [
                ('route', 'Brevo HTTPS API, port 443'),
                ('BREVO_API_KEY',
                 'set' if getattr(settings, 'BREVO_API_KEY', '') else '(unset)'),
            ]
        else:
            rows += [
                ('route', 'SMTP, port ' + str(getattr(settings, 'EMAIL_PORT', ''))),
                ('EMAIL_HOST', host or '(unset)'),
                ('EMAIL_HOST_PASSWORD',
                 'set' if getattr(settings, 'EMAIL_HOST_PASSWORD', '') else '(unset)'),
                ('EMAIL_USE_TLS', getattr(settings, 'EMAIL_USE_TLS', '')),
                ('EMAIL_USE_SSL', getattr(settings, 'EMAIL_USE_SSL', '')),
            ]
        rows += [
            ('EMAIL_HOST_USER', getattr(settings, 'EMAIL_HOST_USER', '') or '(unset)'),
            ('DEFAULT_FROM_EMAIL', getattr(settings, 'DEFAULT_FROM_EMAIL', '')),
            ('SITE_URL', getattr(settings, 'SITE_URL', '') or '(unset)'),
        ]
        for label, value in rows:
            self.stdout.write(f'  {label:22} {value}')
        self.stdout.write('')

        if backend == CONSOLE or not (over_http or host):
            raise CommandError(
                'Neither BREVO_API_KEY nor EMAIL_HOST is set, so Django is using '
                'the console backend: messages are printed to this log and '
                'nothing is delivered to anyone. That is correct on a laptop and '
                'in the test suite. On a deployment it means every applicant '
                'notice and every address confirmation has been going nowhere.\n\n'
                'On Render set BREVO_API_KEY. The free plan blocks outbound SMTP '
                '— ports 25, 465 and 587 — so EMAIL_HOST delivers nothing '
                'there however carefully it is filled in, and Brevo goes out over '
                'HTTPS instead. Set EMAIL_HOST_USER to the sender address you '
                'verified with Brevo.\n'
                'Where SMTP is reachable, set EMAIL_HOST, EMAIL_HOST_USER and '
                'EMAIL_HOST_PASSWORD instead.\n'
                'Both are sync:false in render.yaml, so Render never prompts for '
                'them. Then run this again.'
            )

        connection = get_connection(fail_silently=False)
        if not over_http:
            self.stdout.write(f'Connecting to {host}...')
            try:
                connection.open()
            except Exception as exc:
                raise CommandError(self._explain('Could not connect', exc))
            self.stdout.write(self.style.SUCCESS('  connected and authenticated'))

        self.stdout.write(f'Sending to {to}...')
        try:
            sent = send_mail(
                subject='[BiPSU SRMS] Test message',
                message=(
                    'This is a test from the BiPSU Scholarship Records Management '
                    'System.\n\nIf you are reading it in an inbox, the mail '
                    'configuration works: applicants will be told what the office '
                    'decided, and registrants can confirm their address.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to],
                fail_silently=False,
                connection=connection,
            )
        except Exception as exc:
            raise CommandError(self._explain('The message was refused', exc))
        finally:
            connection.close()

        if not sent:
            raise CommandError(
                'The backend reported that no message was sent, without raising. '
                'Check the mail provider\'s own logs for the account in '
                'EMAIL_HOST_USER — for Brevo that is Transactional > Logs.'
            )

        self.stdout.write(self.style.SUCCESS(f'  accepted for delivery to {to}'))
        self.stdout.write('')
        self.stdout.write(
            'The server accepted it. That is not the same as it arriving — check '
            'the inbox, and the spam folder. If it is not in either, the mail '
            'provider accepted and then dropped it, and their sending log for '
            f'{settings.EMAIL_HOST_USER or "this account"} will say why.'
        )
        if not getattr(settings, 'SITE_URL', ''):
            self.stdout.write(self.style.WARNING(
                'SITE_URL is unset. Mail still sends, but a confirmation link '
                'built without it falls back to the request host, which is wrong '
                'behind a proxy. Set it to the public URL.'
            ))

    def _explain(self, headline, exc):
        name = type(exc).__name__
        lines = [f'{headline}: {name}: {exc}']
        for needle, hint in HINTS:
            if needle.lower() in name.lower() or needle.lower() in str(exc).lower():
                lines.append('')
                lines.append(hint)
                break
        return '\n'.join(lines)
