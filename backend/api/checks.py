"""Django system checks for configuration that fails quietly.

Everything here is a warning rather than an error: the site runs fine without
it. That is exactly why it is worth reporting at deploy time instead of
discovering when an applicant says they were never told anything.
"""

from django.conf import settings
from django.core.checks import Warning, register


@register()
def email_is_configured_in_production(app_configs, **kwargs):
    """Warn when nothing will actually send mail.

    A warning rather than an error, because the site runs perfectly
    without mail: the console backend accepts every message, writes it to
    the log and delivers it to nobody, raising nothing. That is the
    failure worth catching at deploy time instead of discovering when an
    applicant says they were never told.
    """
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if (settings.DEBUG
            or getattr(settings, 'EMAIL_ENABLED', False)
            or backend.endswith('locmem.EmailBackend')):
        return []

    return [
        Warning(
            'Neither BREVO_API_KEY nor EMAIL_HOST is set, so no email will be sent.',
            hint=(
                'Django is using the console backend: every applicant notice '
                'and every address confirmation is written to the service log '
                'and delivered to nobody, without raising an error. The site '
                'runs fine otherwise, which is why this is a warning.\n'
                'On Render, set BREVO_API_KEY. The free plan blocks outbound '
                'SMTP — ports 25, 465 and 587 — so EMAIL_HOST can be '
                'configured perfectly there and still deliver nothing, which '
                'is exactly what it looks like from here. Brevo goes out over '
                'HTTPS instead. Set EMAIL_HOST_USER to the sender address you '
                'verified with Brevo; it refuses any other.\n'
                'Where SMTP is actually reachable — a laptop, a paid '
                'instance, a mail server of the university’s own — set '
                'EMAIL_HOST, EMAIL_HOST_USER and EMAIL_HOST_PASSWORD instead.\n'
                'Either way, the SDSO’s Account Verification page has an '
                'Email panel showing which route is live and what became of '
                'the last send, and a button to send a test — which is the '
                'same answer as `python manage.py check_email`, on a '
                'deployment with no shell to run it in.'
            ),
            id='api.W001',
        )
    ]
