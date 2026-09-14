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
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0032_backfill_staff_profiles'),
    ]

    operations = [
        migrations.RunPython(fill_school, noop),
    ]
