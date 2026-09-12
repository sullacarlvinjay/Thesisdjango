"""Remove the student records that approving a Staff Scholarship used to invent.

Approving a BiPSU Staff application on the Affirmative/Staff queue used to build
a Django account with ``role='student'``, a ``StudentProfile`` numbered
``AFF-<id>`` where the employee had no student number, and an ``Application``
nothing reads. The award itself was always the ``AffirmativeStaffApplication``,
which is what the Staff archive tab, the masterlist's BiPSU STAFF block and the
reports read — so the student record was pure surplus, and it put a BiPSU
employee on My Students, on the No Scholarship archive tab, and on the TES
recommendation the SDSO sends onward to UniFAST.

The view no longer does that. This clears up what it already made.

    python manage.py prune_staff_student_profiles            # show, change nothing
    python manage.py prune_staff_student_profiles --delete    # act

**Nothing is deleted without ``--delete``.** The default run is a report, so the
list can be read before anything goes.

Two tiers, and only the first is ever removed:

* **Certain** — the account's address owns a Staff application that the
  applicant filed **for themselves** (``is_nsu_staff``), and the profile has
  done nothing as a student. An employee applying on their own behalf is not a
  BiPSU student under any reading, so the profile can only be the invented one.
* **Worth a look** — everything else that touches a Staff application: a
  *dependent's* claim, or a profile that has been used. A dependent may well be
  a genuine BiPSU student, and a profile with a renewal or a sign-in behind it
  belongs to somebody. Listed for a person to judge, never touched.

Deliberately **not** a rule: "the student number starts ``AFF-``". Approving an
*Affirmative* application still mints one of those, and an Affirmative scholar
is a real student — see the note in vpsea_affirmative_applications. Pruning on
the prefix alone would take them out with the employees.

The award survives either way: deleting the account cannot reach the
``AffirmativeStaffApplication``, which is a separate row with no foreign key to
it.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import (
    AcademicRenewal, AffirmativeStaffApplication, Application,
    ScholarshipLinkRequest, StudentProfile,
)


def student_side_activity(profile):
    """What this profile has done as a student, as a list of short phrases.

    A phantom has none. Anything here means a person has been using the account
    as a student, and the row is not the throwaway this command is about — so it
    is reported beside the row rather than left for the operator to guess at.
    """
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
        # The employee applying on their own behalf, by address. A dependent's
        # claim is kept apart: the dependent is a different person from the
        # employee, and may be a student in their own right.
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
                # The account, so the cascade takes the profile, its detail
                # rows and its notifications with it. ActivityLog.user is
                # SET_NULL, so the office's record of what was done survives.
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
