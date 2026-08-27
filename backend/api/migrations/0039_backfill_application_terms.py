"""Move the term, provenance and reporting values out of Application.form_data
into the columns added by 0038.

Non-destructive on purpose: the promoted keys are *copied*, not removed, so this
migration is reversible and any reader still going through ``form_data`` keeps
working while the call sites are converted. The one thing that is deleted is
``csrfmiddlewaretoken``, which ``request.POST.dict()`` swept into every
student-submitted row and which has no business being stored at all.

Rows created by the office (link approvals, TES approvals, renewals) carry an
``academic_year``. Student-submitted rows carry no term key whatever — that is
the bug this whole change exists to fix — so their term is derived from the row's
own ``submitted_at`` rather than from whatever the active setting happens to say
today. BiPSU's 1st semester runs from August, which is the boundary used below.
"""
from django.db import migrations

FIRST_SEM_START_MONTH = 8

# Mirrors constants.APPLICATION_SOURCES. Inlined so the migration keeps working
# if that list is later changed.
KNOWN_SOURCES = {'portal', 'link', 'tes_application', 'renewal', 'import'}


def parse_label(label):
    """'26-1' -> ('2026-2027', '1st Semester'). Mirrors SystemSettings.parse_label.

    Reimplemented here because historical models carry fields, not methods, and
    a data migration must not depend on today's version of that helper.
    """
    try:
        yy, sem = label.split('-')
        start = 2000 + int(yy)
        return f'{start}-{start + 1}', ('1st Semester' if sem == '1' else '2nd Semester')
    except (ValueError, AttributeError):
        return label, ''


def label_for(school_year, semester):
    """'2026-2027' + '1st Semester' -> '26-1'."""
    try:
        start = int(str(school_year).split('-')[0])
        return f"{start - 2000}-{'1' if semester == '1st Semester' else '2'}"
    except (ValueError, IndexError, AttributeError):
        return ''


def term_from_date(when):
    """The academic term a submission date falls in."""
    if not when:
        return '', ''
    if when.month >= FIRST_SEM_START_MONTH:
        return f'{when.year}-{when.year + 1}', '1st Semester'
    return f'{when.year - 1}-{when.year}', '2nd Semester'


def forwards(apps, schema_editor):
    Application = apps.get_model('api', 'Application')
    ArchiveRecord = apps.get_model('api', 'ArchiveRecord')
    TESApplication = apps.get_model('api', 'TESApplication')

    archive_ids = set(ArchiveRecord.objects.values_list('id', flat=True))
    tes_ids = set(TESApplication.objects.values_list('id', flat=True))

    stats = {'from_form_data': 0, 'from_submitted_at': 0, 'csrf_stripped': 0,
             'archive_fk': 0, 'tes_fk': 0}

    for app in Application.objects.all():
        fd = app.form_data if isinstance(app.form_data, dict) else {}

        # ── Term. The office wrote 'academic_year'; a couple of paths wrote
        # 'school_year'. Either may hold the expanded form or the short label.
        raw = fd.get('academic_year') or fd.get('school_year') or ''
        semester = fd.get('semester') or ''
        if raw:
            if '-' in str(raw) and len(str(raw).split('-')[0]) == 2:
                school_year, parsed_sem = parse_label(raw)
                semester = semester or parsed_sem
            else:
                school_year = str(raw)
            stats['from_form_data'] += 1
        else:
            school_year, semester = term_from_date(app.submitted_at)
            if school_year:
                stats['from_submitted_at'] += 1

        app.school_year = school_year
        app.semester = semester
        app.term_label = label_for(school_year, semester)

        # ── Provenance and reporting columns.
        source = fd.get('source') or 'portal'
        app.source = source if source in KNOWN_SOURCES else 'portal'
        app.award_number = fd.get('award_number') or ''
        app.congress_district = fd.get('congress_district') or ''

        # ── Foreign keys that were integers inside the JSON. Only adopt an id
        # that still resolves; a dangling one is exactly what this replaces.
        claimed = fd.get('claimed_archive_id')
        if claimed in archive_ids:
            app.claimed_archive_id = claimed
            stats['archive_fk'] += 1
        tes = fd.get('tes_application_id')
        if tes in tes_ids:
            app.tes_application_id = tes
            stats['tes_fk'] += 1

        # ── The one deletion: session credential material swept in by
        # form_data=request.POST.dict().
        if isinstance(app.form_data, dict) and 'csrfmiddlewaretoken' in app.form_data:
            app.form_data.pop('csrfmiddlewaretoken')
            stats['csrf_stripped'] += 1

        app.save(update_fields=[
            'term_label', 'school_year', 'semester', 'source', 'award_number',
            'congress_district', 'claimed_archive', 'tes_application', 'form_data',
        ])

    total = Application.objects.count()
    print(f'\n  backfilled {total} application(s): '
          f"{stats['from_form_data']} term from form_data, "
          f"{stats['from_submitted_at']} term from submitted_at, "
          f"{stats['archive_fk']} archive FK, {stats['tes_fk']} TES FK, "
          f"{stats['csrf_stripped']} CSRF token(s) stripped")


def backwards(apps, schema_editor):
    """Clear the promoted columns. The values they came from are still in
    form_data — this migration never removed them — so nothing is lost."""
    Application = apps.get_model('api', 'Application')
    Application.objects.all().update(
        term_label='', school_year='', semester='', source='portal',
        award_number='', congress_district='',
        claimed_archive=None, tes_application=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0038_application_term_columns'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
