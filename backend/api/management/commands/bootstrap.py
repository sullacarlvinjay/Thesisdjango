"""Prepare a freshly migrated database for real use.

Distinct from ``seed``, which invents students and applications to look at on a
laptop. This creates only what an empty deployment cannot work without: the
system settings row, the scholarship catalogue, and the two office accounts
that let anyone sign in at all.

Safe to run on every deploy, which is why build.sh calls it: everything is
get_or_create, and an existing account is left exactly as it is. In particular
a password already in use is never overwritten — an operator who changed it in
the admin would otherwise find it silently reverted on the next deploy.

Passwords come from the environment because Render's free plan has no shell,
so ``createsuperuser`` cannot be run interactively. No password is ever
hard-coded here; an office whose password variable is unset is skipped and
reported, rather than created with something guessable.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from ...catalogue import ensure_scholarships

User = get_user_model()

# email variable, password variable, defaults for a newly created account.
OFFICES = [
    ('SDSO_EMAIL', 'SDSO_PASSWORD', {
        'default_email': 'sdso@bipsu.edu.ph',
        'label': 'SDSO (VPSEA office)',
        'first_name': 'SDSO',
        'last_name': 'Office',
        'role': 'vpsea',
        # The SDSO runs the system, so this is the account that also reaches
        # /admin/ when something needs fixing directly.
        'is_staff': True,
        'is_superuser': True,
    }),
    ('UNIFAST_EMAIL', 'UNIFAST_PASSWORD', {
        'default_email': 'unifast@bipsu.edu.ph',
        'label': 'UniFAST office',
        'first_name': 'UniFAST',
        'last_name': 'Office',
        'role': 'unifast',
        'is_staff': False,
        'is_superuser': False,
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
            # Worth printing rather than counting: this is what corrects a
            # programme filed under the wrong office, and the deploy log is the
            # only place anyone would see it happen.
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
                # Deliberately not touching the password: it may have been
                # changed since, and a deploy is not a password reset.
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
