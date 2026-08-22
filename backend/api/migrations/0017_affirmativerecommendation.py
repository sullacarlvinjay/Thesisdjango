from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0016_studentprofile_affirmative_eligibility'),
    ]

    operations = [
        migrations.CreateModel(
            name='AffirmativeRecommendation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shs_gpa_snapshot', models.FloatField()),
                ('suc_exam_score_snapshot', models.FloatField()),
                ('shs_gpa_passing', models.FloatField(default=75.0)),
                ('fit_score', models.FloatField(default=0.0)),
                ('status', models.CharField(
                    choices=[
                        ('Recommended', 'Recommended'),
                        ('Endorsed', 'Endorsed'),
                        ('Disqualified', 'Disqualified'),
                    ],
                    default='Recommended',
                    max_length=20,
                )),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='affirmative_recommendation',
                    to='api.studentprofile',
                )),
            ],
            options={
                'ordering': ['-fit_score', 'student__user__last_name'],
            },
        ),
    ]
