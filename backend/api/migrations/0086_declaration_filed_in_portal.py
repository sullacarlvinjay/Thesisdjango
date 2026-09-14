from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0085_imported_scholar_ched_tier'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshiplinkrequest',
            name='filed_in_portal',
            field=models.BooleanField(default=False, help_text='Declared from the student portal rather than on the registration form.'),
        ),
    ]
