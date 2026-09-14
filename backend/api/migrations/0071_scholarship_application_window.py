from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0070_tes_grantee_batch_on_review'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarship',
            name='applications_open_days',
            field=models.PositiveIntegerField(blank=True, help_text='How many days it stays open, counting the first. Blank means no closing date.', null=True),
        ),
        migrations.AddField(
            model_name='scholarship',
            name='applications_open_on',
            field=models.DateField(blank=True, help_text='First day students may apply. Blank leaves the programme always open.', null=True),
        ),
    ]
