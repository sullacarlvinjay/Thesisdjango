from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0077_last_mail_attempt'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='partnerapplicationform',
            name='one_form_per_partner_programme',
        ),
        migrations.RemoveConstraint(
            model_name='partnerformsubmission',
            name='one_partner_submission_per_term',
        ),
        migrations.RemoveField(
            model_name='partnerformsubmission',
            name='form',
        ),
        migrations.RemoveField(
            model_name='partnerformfield',
            name='form',
        ),
        migrations.RemoveField(
            model_name='partnerformsubmission',
            name='student',
        ),
        migrations.DeleteModel(
            name='PartnerApplicationForm',
        ),
        migrations.DeleteModel(
            name='PartnerFormField',
        ),
        migrations.DeleteModel(
            name='PartnerFormSubmission',
        ),
    ]
