from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0043_entity_choices_and_ordering'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshiplinkrequest',
            name='award_tier',
            field=models.CharField(blank=True, choices=[('Full', 'Full Merit / Full Scholar'), ('Half', 'Half Merit / Partial Scholar')], max_length=10),
        ),
    ]
