"""Give the employees who registered before the stamp a term to show.

``StaffProfile`` only became term-stamped in 0101, so every employee who
registered before it has no term and reads as a dash in the office's account
list. The term they actually signed up in was never recorded and cannot be
recovered — nothing keeps a dated history of which term was active when — so
this is the office deciding what those rows should say, not a reconstruction.

Only rows carrying no term at all are touched. An employee stamped by
``fill_term`` since 0101 keeps whatever it stamped.

Render's free plan has no shell, so there is no way to run this by hand against
the deployed database. ``build.sh`` runs ``migrate`` on every deploy, which is
why a data migration is how production data gets corrected here.
"""

from django.db import migrations

TERM_LABEL = '26-1'
SCHOOL_YEAR = '2026-2027'
SEMESTER = '1st Semester'


def stamp_unstamped_staff(apps, schema_editor):
    """Stamp the employees carrying no term with the term the office named."""
    apps.get_model('api', 'StaffProfile').objects.filter(
        term_label='', school_year='',
    ).update(
        term_label=TERM_LABEL, school_year=SCHOOL_YEAR, semester=SEMESTER,
    )


def leave_them_stamped(apps, schema_editor):
    """Reversing does not unstamp anybody.

    There is no record of which rows this filled, so clearing every row holding
    this term would also clear the employees who genuinely registered in it.
    Going backwards leaves the stamps in place, as 0098 does.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0101_staffprofile_school_year_staffprofile_semester_and_more'),
    ]

    operations = [
        migrations.RunPython(stamp_unstamped_staff, leave_them_stamped),
    ]
