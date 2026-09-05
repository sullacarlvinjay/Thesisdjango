"""Deploy-time checks for configuration that fails quietly.

The pattern is the one ``manage.py check_storage`` follows: settings.py can only
see whether a variable is *set*, and the interesting failures are the ones where
everything starts perfectly and goes wrong much later, in front of a student.

Mail is the worst of those. With EMAIL_HOST unset Django swaps in the console
backend, which accepts every message, writes it to the service log and reports
success. On a laptop and in the test suite that is exactly right. On a
deployment it means every decision notice and every address confirmation has
been going nowhere, and nothing anywhere says so.

A warning rather than an error, and deliberately: the site is genuinely usable
without mail — the office still reviews applications, students still read
decisions in their portal. Taking a whole deployment down over email would be
the wrong trade. But it should be impossible to deploy without being told.
"""

from django.conf import settings
from django.core.checks import Warning, register


@register()
def email_is_configured_in_production(app_configs, **kwargs):
    """Warn when a real deployment has no mail server.

    Keyed on DEBUG rather than on anything Render-specific: DEBUG=False is what
    'this is not somebody's laptop' means everywhere, and render.yaml sets it.

    The locmem exclusion is not belt-and-braces. Django's test runner forces
    DEBUG=False *and* swaps the mail backend for locmem, so without it every
    single `manage.py test` run would print this warning — and a warning that
    cries wolf on every test run is one nobody reads on the day it matters.
    locmem is the precise signal, because it is the one backend that means
    'these messages are being collected deliberately'.
    """
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if (settings.DEBUG
            or getattr(settings, 'EMAIL_HOST', '')
            or backend.endswith('locmem.EmailBackend')):
        return []

    return [
        Warning(
            'EMAIL_HOST is not set, so no email will be sent.',
            hint=(
                'Django is using the console backend: every applicant notice '
                'and every address confirmation is written to the service log '
                'and delivered to nobody, without raising an error. The site '
                'runs fine otherwise, which is why this is a warning.\n'
                'Set EMAIL_HOST, EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in '
                'the Render dashboard — they are sync:false in render.yaml, so '
                'Render never prompts for them — then prove it with '
                '`python manage.py check_email you@example.com`.'
            ),
            id='api.W001',
        )
    ]
