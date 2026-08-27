"""Fill in the blank StudentProfile.school from the course, where it is certain.

The field was never written by any form — the VPSEA student form collected a
School but the view dropped it — so it is blank on nearly every profile. The
course is on file, and most courses belong to exactly one BiPSU school, so the
school can be recovered for those. Anything that does not match a known course
exactly is left blank for the office to set: a wrong school is worse than none.
"""
from django.db import migrations


def fill_school(apps, schema_editor):
    from api.constants import school_for_course

    StudentProfile = apps.get_model('api', 'StudentProfile')
    for profile in StudentProfile.objects.filter(school=''):
        school = school_for_course(profile.course)
        if school:
            profile.school = school
            profile.save(update_fields=['school'])


def noop(apps, schema_editor):
    """Nothing to undo — blanking these again would throw away good data."""


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0032_backfill_staff_profiles'),
    ]

    operations = [
        migrations.RunPython(fill_school, noop),
    ]
