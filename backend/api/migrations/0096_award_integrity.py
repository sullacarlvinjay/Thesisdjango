from django.db import migrations, models

DUPLICATE_HEADING = (
    'Some award numbers are recorded twice for the same programme and term, so '
    'the unique constraints cannot be added:'
)

DUPLICATE_HINT = (
    'Settle each row above with the office, then deploy again. Where a shell is '
    'available, `python manage.py find_duplicate_awards` prints the same list '
    'without waiting for a deploy.'
)

CLASH_LIMIT = 50


def describe_clash(fields, row, programmes):
    parts = []
    for field in fields:
        value = row[field]
        if field == 'scholarship_id':
            value = programmes.get(value, value)
        parts.append(str(value) if value not in ('', None) else '(blank)')
    return ' '.join(parts)


def refuse_duplicate_award_numbers(apps, schema_editor):
    """Stop the migration with something readable if award numbers repeat."""
    from django.db.models import Count

    Application = apps.get_model('api', 'Application')
    ImportedScholar = apps.get_model('api', 'ImportedScholar')
    Scholarship = apps.get_model('api', 'Scholarship')
    ScholarshipLinkRequest = apps.get_model('api', 'ScholarshipLinkRequest')

    programmes = dict(Scholarship.objects.values_list('pk', 'name'))

    checks = (
        ('Application', Application.objects.exclude(award_number=''),
         ['scholarship_id', 'school_year', 'semester', 'award_number']),
        ('ImportedScholar', ImportedScholar.objects.exclude(award_number=''),
         ['scholarship_type', 'term_label', 'award_number']),
        ('ScholarshipLinkRequest',
         ScholarshipLinkRequest.objects.filter(status='Approved')
         .exclude(award_number=''),
         ['scholarship_type', 'term_label', 'award_number']),
    )

    clashes = []
    for label, queryset, fields in checks:
        rows = (queryset.values(*fields).annotate(seen=Count('pk'))
                .filter(seen__gt=1).order_by(*fields))
        for row in rows:
            detail = describe_clash(fields, row, programmes)
            clashes.append(
                f"    {label}: {detail} — recorded {row['seen']} times")

    if clashes:
        listed = clashes[:CLASH_LIMIT]
        if len(clashes) > CLASH_LIMIT:
            listed.append(f'    ... and {len(clashes) - CLASH_LIMIT} more')
        raise RuntimeError('\n'.join(
            [DUPLICATE_HEADING, ''] + listed + ['', DUPLICATE_HINT]))


class Migration(migrations.Migration):
    """An award number identifies one award, and only one.

    There is deliberately no constraint here on a student holding two
    benefits in one term. A student who really does hold a DOST award and a
    CHED award is the problem this system exists to surface, and a database
    that refused to store the second one could not show the office the first
    thing about it. That case is warned about before the office approves it,
    and listed afterwards by ``manage.py find_duplicate_awards``.
    """

    dependencies = [
        ('api', '0095_enrollmentdata_study_load'),
    ]

    operations = [
        migrations.RunPython(refuse_duplicate_award_numbers,
                             migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='application',
            constraint=models.UniqueConstraint(
                condition=models.Q(('award_number', ''), _negated=True),
                fields=('scholarship', 'school_year', 'semester', 'award_number'),
                name='one_award_number_per_programme_term'),
        ),
        migrations.AddConstraint(
            model_name='importedscholar',
            constraint=models.UniqueConstraint(
                condition=models.Q(('award_number', ''), _negated=True),
                fields=('scholarship_type', 'term_label', 'award_number'),
                name='one_imported_award_number_per_term'),
        ),
        migrations.AddConstraint(
            model_name='scholarshiplinkrequest',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'Approved'),
                                   models.Q(('award_number', ''), _negated=True)),
                fields=('scholarship_type', 'term_label', 'award_number'),
                name='one_approved_link_award_number_per_term'),
        ),
    ]
