from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0083_user_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='educationalbackground',
            name='highschool_is_public',
            field=models.BooleanField(blank=True, help_text='Was the high school above a public school? Null means not yet asked.', null=True),
        ),
        migrations.AddField(
            model_name='socioeconomicprofile',
            name='is_from_depressed_area',
            field=models.BooleanField(blank=True, help_text='Declared to live in a depressed area, for the office to verify. Null means not yet asked.', null=True),
        ),
    ]
