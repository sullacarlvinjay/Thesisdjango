from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0076_staff_scholarship_declaration'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='last_mail_attempt_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='last_mail_error',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='last_mail_subject',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='last_mail_to',
            field=models.CharField(blank=True, max_length=254),
        ),
    ]
