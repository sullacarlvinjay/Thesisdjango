from django.db import migrations


def move_staff_to_internal(apps, schema_editor):
    Scholarship = apps.get_model('api', 'Scholarship')
    Scholarship.objects.filter(type='Staff').update(group='internal')


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0030_add_middle_name_to_studentprofile'),
    ]

    operations = [
        migrations.RunPython(move_staff_to_internal, migrations.RunPython.noop),
    ]
