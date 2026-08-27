"""Re-date the applications that were stamped with the apply form's hard-coded term.

``templates/student/apply_academic.html`` shipped the School Year field as
``value="2024-2025"`` and the Semester field as ``value="2nd Semester"`` —
literals in the markup, not values from SystemSettings. Every academic
application ever submitted therefore claimed SY 2024-2025 no matter when it was
actually sent, and 0039 faithfully copied that claim into the new columns.

The template is fixed. This corrects the rows it mislabelled, and only those:
a row qualifies solely when it carries that exact literal *and* its own
``submitted_at`` falls outside the school year it claims. An application
genuinely submitted during 2024-2025 keeps its term untouched.

Reversible: backwards() puts the claimed term back from form_data, which 0039
never removed.
"""
from django.db import migrations

HARDCODED_SCHOOL_YEAR = '2024-2025'
FIRST_SEM_START_MONTH = 8


def term_from_date(when):
    """The academic term a date actually falls in. August starts 1st semester."""
    if when.month >= FIRST_SEM_START_MONTH:
        return f'{when.year}-{when.year + 1}', '1st Semester'
    return f'{when.year - 1}-{when.year}', '2nd Semester'


def label_for(school_year, semester):
    start = int(str(school_year).split('-')[0])
    return f"{start - 2000}-{'1' if semester == '1st Semester' else '2'}"


def forwards(apps, schema_editor):
    Application = apps.get_model('api', 'Application')

    corrected = []
    for app in Application.objects.filter(school_year=HARDCODED_SCHOOL_YEAR):
        fd = app.form_data if isinstance(app.form_data, dict) else {}
        # Only rows whose term came from the template literal, not from an
        # office path that legitimately set the same school year.
        if fd.get('school_year') != HARDCODED_SCHOOL_YEAR:
            continue
        if not app.submitted_at:
            continue
        actual_sy, actual_sem = term_from_date(app.submitted_at)
        if actual_sy == HARDCODED_SCHOOL_YEAR:
            continue  # genuinely submitted during the year it claims

        was = app.term_label
        app.school_year = actual_sy
        app.semester = actual_sem
        app.term_label = label_for(actual_sy, actual_sem)
        app.save(update_fields=['school_year', 'semester', 'term_label'])
        corrected.append((app.id, was, app.term_label, app.submitted_at))

    if corrected:
        print(f'\n  re-dated {len(corrected)} application(s) stamped by the hard-coded form:')
        for app_id, was, now, when in corrected:
            print(f'    application {app_id}: {was} -> {now}  (submitted {when})')
    else:
        print('\n  no hard-coded terms to correct')


def backwards(apps, schema_editor):
    """Restore the term the row claimed, from the copy 0039 left in form_data."""
    Application = apps.get_model('api', 'Application')
    for app in Application.objects.all():
        fd = app.form_data if isinstance(app.form_data, dict) else {}
        if fd.get('school_year') != HARDCODED_SCHOOL_YEAR:
            continue
        app.school_year = HARDCODED_SCHOOL_YEAR
        app.semester = fd.get('semester') or ''
        app.term_label = label_for(HARDCODED_SCHOOL_YEAR, app.semester)
        app.save(update_fields=['school_year', 'semester', 'term_label'])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0040_award_uniqueness'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
