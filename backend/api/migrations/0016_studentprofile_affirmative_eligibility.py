from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0015_add_tes_application'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='shs_gpa',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='shs_gpa_cert',
            field=models.FileField(blank=True, null=True, upload_to='profile/shs_cert/'),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='suc_exam_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='suc_exam_cert',
            field=models.FileField(blank=True, null=True, upload_to='profile/suc_cert/'),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='is_tes_beneficiary',
            field=models.BooleanField(default=False),
        ),
    ]
