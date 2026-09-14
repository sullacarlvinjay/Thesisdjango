from django.conf import settings
from django.core.checks import Warning, register


@register()
def email_is_configured_in_production(app_configs, **kwargs):
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
