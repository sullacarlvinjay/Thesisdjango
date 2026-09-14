from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0053_drop_draft_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_confirmation_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=True),
        ),
    ]
