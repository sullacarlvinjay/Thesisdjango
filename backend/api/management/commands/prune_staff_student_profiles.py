from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import (
    AcademicRenewal, AffirmativeStaffApplication, Application,
    ScholarshipLinkRequest, StudentProfile,
)


def student_side_activity(profile):
    activity = []

    awards = list(Application.objects.filter(student=profile)
                  .select_related('scholarship'))
    outside = [a for a in awards
               if a.scholarship.type not in ('Staff', 'Affirmative')]
    if outside:
        activity.append('holds ' + ', '.join(sorted({a.scholarship.type
                                                     for a in outside})))
    if AcademicRenewal.objects.filter(student=profile).exists():
        activity.append('submitted a renewal')
    if ScholarshipLinkRequest.objects.filter(student=profile).exists():
        activity.append('declared a scholarship')
    if profile.user.last_login is not None:
        activity.append(f'signed in ({profile.user.last_login:%Y-%m-%d})')
    return activity


class Command(BaseCommand):
    help = ('List — and with --delete, remove — the student accounts that '
            'approving a BiPSU Staff Scholarship used to invent.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete', action='store_true',
            help='Actually remove them. Without it nothing is written.')

    def handle(self, *args, **options):
        own_claim, other_claim = set(), set()
        for application in (AffirmativeStaffApplication.objects
                            .filter(qualified_for='Staff').exclude(email='')):
            address = application.email.lower()
            (own_claim if application.is_nsu_staff else other_claim).add(address)

        certain, look = [], []
        for profile in (StudentProfile.objects.select_related('user')
                        .order_by('student_id')):
            address = (profile.user.email or '').lower()
            if address not in own_claim and address not in other_claim:
                continue
            activity = student_side_activity(profile)
            entry = (profile, activity)
            if address in own_claim and not activity:
                certain.append(entry)
            else:
                look.append(entry)

        self._report("Certain — the employee's own Staff claim, and the profile "
                     'has never been used as a student', certain)
        self._report("Worth a look — a dependent's claim, or a profile somebody "
                     'has used. Not touched.', look)

        if not certain:
            self.stdout.write(self.style.SUCCESS(
                '\nNothing to remove.'))
            return

        if not options['delete']:
            self.stdout.write(
                f'\nDry run. Re-run with --delete to remove the '
                f'{len(certain)} certain row(s).')
            return

        with transaction.atomic():
            removed = 0
            for profile, _activity in certain:
                profile.user.delete()
                removed += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nRemoved {removed} invented student record(s). '
            f'The Staff awards themselves are untouched — they live on '
            f'AffirmativeStaffApplication.'))

    def _report(self, heading, entries):
        self.stdout.write(f'\n{heading}: {len(entries)}')
        for profile, activity in entries:
            note = ('  <- ' + '; '.join(activity)) if activity else ''
            self.stdout.write(
                f'   {profile.student_id:<14} {profile.user.email:<34} '
                f'{profile.user.get_full_name()}{note}')
