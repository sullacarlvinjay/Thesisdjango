"""Drop the 'Endorsed' recommendation status.

The Student Ranking page recommends; the award itself is recorded on the
Archives page like every other programme's, so an endorsement flag here was a
second, private status for a decision already written down somewhere the reports
read. It went with the applicant list, which ranked a submission nobody can make.

Changing the choices alone would leave any row already saying 'Endorsed' holding
a value the field no longer offers -- valid in the database, invalid to every
form and to `get_status_display`. Those rows go back to 'Recommended', which is
what they were before somebody pressed the button, and is what the rules will
say about them on the next re-evaluation anyway.
"""
from django.db import migrations, models


def endorsed_back_to_recommended(apps, schema_editor):
    Recommendation = apps.get_model('api', 'AffirmativeRecommendation')
    Recommendation.objects.filter(status='Endorsed').update(status='Recommended')


def noop(apps, schema_editor):
    """Nothing to undo: 'Recommended' is a value both versions of the field hold,
    and which of them had been endorsed is not recoverable."""


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0060_staff_scholar_course'),
    ]

    operations = [
        migrations.RunPython(endorsed_back_to_recommended, noop),
        migrations.AlterField(
            model_name='affirmativerecommendation',
            name='status',
            field=models.CharField(choices=[('Recommended', 'Recommended'), ('Disqualified', 'Disqualified')], default='Recommended', max_length=20),
        ),
    ]
