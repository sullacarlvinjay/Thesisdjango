from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0068_tes_checks_issued'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tesapplication',
            name='batch',
        ),
    ]
