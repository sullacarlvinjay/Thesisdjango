"""Report the duplicate benefits the new database constraints forbid.

Run this before deploying the migration that adds them. A constraint cannot
be added to a table that already violates it, so anything this prints has to
be settled by the office first.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count


class Command(BaseCommand):
    help = ('List students holding more than one award for a term, and award '
            'numbers recorded twice for the same programme and term.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--fail', action='store_true',
            help='Exit non-zero when anything is found, for use in a deploy gate.',
        )

    def handle(self, *args, **options):
        found = 0
        found += self._duplicate_benefits()
        found += self._duplicate_award_numbers()

        if not found:
            self.stdout.write(self.style.SUCCESS(
                '  awards: no duplicate benefits and no repeated award numbers'))
            return

        self.stdout.write(self.style.WARNING(
            f'  awards: {found} conflict(s). Settle these before migrating — the '
            'database will refuse to hold them once the constraints are on.'))
        if options['fail']:
            raise CommandError('Duplicate awards on file.')

    def _duplicate_benefits(self):
        """Students holding two conflicting national grants in one term.

        Scoped to ``CONFLICTING_BENEFIT_TYPES`` so this and the warning the
        office sees at approval time answer the same question. An internal
        BiPSU scholarship alongside a national grant is not a duplicate
        benefit and is not reported as one.
        """
        from api.constants import ALWAYS_HOLDABLE_TYPES, CONFLICTING_BENEFIT_TYPES
        from api.models import Application

        conflicting = (
            Application.objects
            .filter(status='Approved',
                    scholarship__type__in=CONFLICTING_BENEFIT_TYPES)
            .exclude(scholarship__type__in=ALWAYS_HOLDABLE_TYPES)
        )
        rows = list(
            conflicting
            .values('student', 'school_year', 'semester')
            .annotate(held=Count('pk'))
            .filter(held__gt=1)
            .order_by('student')
        )
        if not rows:
            return 0

        self.stdout.write(self.style.WARNING(
            f'  duplicate benefits ({len(rows)}):'))
        for row in rows:
            awards = conflicting.filter(
                student=row['student'], school_year=row['school_year'],
                semester=row['semester'],
            ).select_related('student__user', 'scholarship')
            names = ', '.join(sorted(a.scholarship.type for a in awards))
            who = awards.first().student
            self.stdout.write(
                f"    {who} — {row['school_year']} {row['semester']}: {names}")
        return len(rows)

    def _duplicate_award_numbers(self):
        """Award numbers recorded twice for one programme and term."""
        from api.models import Application, ImportedScholar, ScholarshipLinkRequest

        checks = (
            ('Application', Application.objects.exclude(award_number=''),
             ['scholarship__type', 'school_year', 'semester', 'award_number']),
            ('ImportedScholar', ImportedScholar.objects.exclude(award_number=''),
             ['scholarship_type', 'term_label', 'award_number']),
            ('ScholarshipLinkRequest',
             ScholarshipLinkRequest.objects.filter(status='Approved')
             .exclude(award_number=''),
             ['scholarship_type', 'term_label', 'award_number']),
        )

        total = 0
        for label, queryset, fields in checks:
            rows = list(
                queryset.values(*fields).annotate(seen=Count('pk')).filter(seen__gt=1)
            )
            if not rows:
                continue
            total += len(rows)
            self.stdout.write(self.style.WARNING(
                f'  repeated award numbers in {label} ({len(rows)}):'))
            for row in rows:
                detail = ' '.join(str(row[f]) for f in fields if row[f])
                self.stdout.write(f"    {detail} — recorded {row['seen']} times")
        return total
