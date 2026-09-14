from django.db import migrations, models


def endorsed_back_to_recommended(apps, schema_editor):
    Recommendation = apps.get_model('api', 'AffirmativeRecommendation')
    Recommendation.objects.filter(status='Endorsed').update(status='Recommended')


def noop(apps, schema_editor):
    pass


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
