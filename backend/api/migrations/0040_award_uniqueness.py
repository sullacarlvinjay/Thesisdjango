from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0039_backfill_application_terms'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='application',
            constraint=models.UniqueConstraint(
                fields=('student', 'scholarship', 'school_year', 'semester'),
                name='one_award_per_student_scholarship_term',
            ),
        ),
        migrations.AddConstraint(
            model_name='tesapplication',
            constraint=models.UniqueConstraint(
                fields=('student',),
                name='one_tes_application_per_student',
            ),
        ),
    ]
