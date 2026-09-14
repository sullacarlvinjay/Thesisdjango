from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0054_email_confirmation'),
    ]

    operations = [
        migrations.AddField(
            model_name='tesapplication',
            name='four_ps_id',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='tesapplication',
            name='philsys_id',
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
