"""Two windows per programme, and a switch on each.

Applications and renewals are two announcements — an office opens applications
for the incoming batch and renewals for the continuing scholars, on different
dates — and until now there was one window, for applications only. Renewals were
open permanently because nothing could close them.

The switches are the other half. A window could say "not yet" or "no longer",
but there was no way to say "not this semester" without inventing a date that
had already passed. ``accepting_applications`` and ``accepting_renewals`` are
that answer, and they default to True for the reason the date fields default to
blank: every programme that existed before this migration was open, and a
default that shut them all would have closed the portal on migrate.

Nothing is dropped. The two application columns keep whatever they were set to,
and go on meaning exactly what they meant. What moved is where they are typed —
off the programme's form under Scholarship Programs and onto the Applications
and Renewal Applications tabs, beside the queue each one governs.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0078_drop_partner_application_forms'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarship',
            name='accepting_applications',
            field=models.BooleanField(default=True, help_text='Off closes applications now, whatever the window below says.'),
        ),
        migrations.AddField(
            model_name='scholarship',
            name='accepting_renewals',
            field=models.BooleanField(default=True, help_text='Off closes renewals now, whatever the window below says.'),
        ),
        migrations.AddField(
            model_name='scholarship',
            name='renewals_open_days',
            field=models.PositiveIntegerField(blank=True, help_text='How many days renewals stay open, counting the first.', null=True),
        ),
        migrations.AddField(
            model_name='scholarship',
            name='renewals_open_on',
            field=models.DateField(blank=True, help_text='First day scholars may renew. Blank leaves renewals always open.', null=True),
        ),
    ]
