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
