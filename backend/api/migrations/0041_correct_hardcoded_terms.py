from django.db import migrations

HARDCODED_SCHOOL_YEAR = '2024-2025'
FIRST_SEM_START_MONTH = 8


def term_from_date(when):
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
        if fd.get('school_year') != HARDCODED_SCHOOL_YEAR:
            continue
        if not app.submitted_at:
            continue
        actual_sy, actual_sem = term_from_date(app.submitted_at)
        if actual_sy == HARDCODED_SCHOOL_YEAR:
            continue

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
