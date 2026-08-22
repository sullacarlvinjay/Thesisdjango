from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_staffrenewal'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='staffrenewal',
            name='certificate_of_grades',
        ),
        migrations.RemoveField(
            model_name='staffrenewal',
            name='certificate_of_enrollment',
        ),
    ]
