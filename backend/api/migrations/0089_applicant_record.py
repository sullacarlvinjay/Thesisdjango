from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0088_signup_source_and_scholarship_stamp'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='AffirmativeStaffApplication',
            new_name='ApplicantRecord',
        ),
    ]
