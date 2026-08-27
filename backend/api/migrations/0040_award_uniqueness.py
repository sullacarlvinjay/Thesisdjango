"""The two uniqueness rules the application code has always enforced by hand.

Deliberately separate from 0038, and after the 0039 backfill: added alongside
the columns they constrain, every pre-existing row would still have had a blank
school_year and semester, and any student holding two awards for one scholarship
would have collided on ('', '').

Both were checked against the working database before this was written — zero
collisions on either. Re-run that check against production before applying:
a duplicate makes this migration fail partway rather than corrupt anything, but
failing partway is still an outage.
"""
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
