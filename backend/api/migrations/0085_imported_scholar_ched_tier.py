from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0084_affirmative_target_groups'),
    ]

    operations = [
        migrations.AddField(
            model_name='importedscholar',
            name='award_tier',
            field=models.CharField(blank=True, choices=[('Full', 'Full Merit / Full Scholar'), ('Half', 'Half Merit / Partial Scholar')], max_length=10),
        ),
    ]
