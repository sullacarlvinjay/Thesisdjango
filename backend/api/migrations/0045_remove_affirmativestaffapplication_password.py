from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0044_scholarshiplinkrequest_award_tier'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='affirmativestaffapplication',
            name='password',
        ),
    ]
