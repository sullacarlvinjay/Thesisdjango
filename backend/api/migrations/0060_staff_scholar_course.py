from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0059_drop_moved_staff_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffeducation',
            name='course',
            field=models.CharField(blank=True, help_text='The programme the employee is enrolled in as a scholar.', max_length=100),
        ),
        migrations.AddField(
            model_name='staffeducation',
            name='year_level',
            field=models.IntegerField(default=1),
        ),
    ]
