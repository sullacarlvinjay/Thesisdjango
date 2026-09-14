from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0062_profile_disability_type'),
    ]

    operations = [
        migrations.RemoveField(model_name='socioeconomicprofile', name='is_pwd'),
        migrations.RemoveField(model_name='socioeconomicprofile', name='is_athlete'),
        migrations.RemoveField(model_name='socioeconomicprofile',
                               name='is_coconut_farmer_family'),
        migrations.RemoveField(model_name='socioeconomicprofile',
                               name='has_other_scholarship'),
    ]
