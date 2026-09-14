import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from ...catalogue import ensure_scholarships

User = get_user_model()

OFFICES = [
    ('SDSO_EMAIL', 'SDSO_PASSWORD', {
        'default_email': 'sdso@bipsu.edu.ph',
        'label': 'SDSO (VPSEA office)',
        'first_name': 'SDSO',
        'last_name': 'Office',
        'role': 'vpsea',
        'is_staff': True,
        'is_superuser': True,
    }),
]


class Command(BaseCommand):
    help = 'Create the system settings, scholarship catalogue and office accounts.'

    def handle(self, *args, **options):
        with transaction.atomic():
            self._settings()
            self._scholarships()
            self._offices()

    def _settings(self):
        from ...models import SystemSettings
        _, created = SystemSettings.objects.get_or_create(pk=1)
        self.stdout.write('  system settings: ' + ('created' if created else 'already present'))

    def _scholarships(self):
        added, updated = ensure_scholarships()
        if added:
            self.stdout.write(self.style.SUCCESS(
                f'  scholarships: added {len(added)} - ' + ', '.join(added)))
        if updated:
            self.stdout.write(self.style.SUCCESS(
                f'  scholarships: corrected {len(updated)} - ' + '; '.join(updated)))
        if not added and not updated:
            self.stdout.write('  scholarships: all present and already correct')

    def _offices(self):
        for email_var, password_var, spec in OFFICES:
            email = os.environ.get(email_var, spec['default_email']).strip().lower()
            password = os.environ.get(password_var, '')
            label = spec['label']

            existing = User.objects.filter(email__iexact=email).first()
            if existing:
                self.stdout.write(f'  {label}: {email} already exists, left alone')
                continue

            if not password:
                self.stdout.write(self.style.WARNING(
                    f'  {label}: SKIPPED — set {password_var} to create {email}. '
                    'No account is created without a password from the environment.'))
                continue

            User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=spec['first_name'],
                last_name=spec['last_name'],
                role=spec['role'],
                is_staff=spec['is_staff'],
                is_superuser=spec['is_superuser'],
            )
            self.stdout.write(self.style.SUCCESS(f'  {label}: created {email}'))
