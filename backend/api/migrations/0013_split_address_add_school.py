from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_studentprofile_elementary_studentprofile_father_name_and_more'),
    ]

    operations = [
        # StudentProfile: add new fields
        migrations.AddField(
            model_name='studentprofile',
            name='school',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='barangay',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='municipality',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='province',
            field=models.CharField(blank=True, max_length=100),
        ),
        # Migrate existing address data into barangay
        migrations.RunSQL(
            "UPDATE api_studentprofile SET barangay = address WHERE address IS NOT NULL AND address != ''",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # StudentProfile: remove old address field
        migrations.RemoveField(
            model_name='studentprofile',
            name='address',
        ),
        # AffirmativeNSUApplication: add new fields
        migrations.AddField(
            model_name='affirmativensuapplication',
            name='school',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='affirmativensuapplication',
            name='barangay',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='affirmativensuapplication',
            name='municipality',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='affirmativensuapplication',
            name='province',
            field=models.CharField(blank=True, max_length=100),
        ),
        # Migrate existing address data into barangay
        migrations.RunSQL(
            "UPDATE api_affirmativensuapplication SET barangay = address WHERE address IS NOT NULL AND address != ''",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # AffirmativeNSUApplication: remove old address field
        migrations.RemoveField(
            model_name='affirmativensuapplication',
            name='address',
        ),
    ]
