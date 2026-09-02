"""Whether a registrant's email address was proved to be theirs.

``email_verified`` defaults to True, so every account that already exists keeps
working and nobody who registered before this gate is locked out of a portal
they were already let into. Only the public registration form sets it False —
see api/email_verify.py.
"""

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
