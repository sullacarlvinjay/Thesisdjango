"""Delete the form a partner designed and everything students answered on it.

**This drops data and cannot be undone.** The SDSO settled what an external
partner's portal is for: reading the archive of its own scholars and taking that
list away. It is not a second place to apply. A funder that wants its own
questions asked asks them on its own site, and the office records the award here
once it is granted — which is what every other externally funded programme
already does.

So the builder, the questions, the student-facing form and the submissions all
go. ``PartnerOffice`` and ``PartnerTableColumns`` stay: who a partner is and how
it lays its own table out are exactly what the reading half needs.

Nothing here ever created an award. A submission was answers and nothing more,
so no ``Application``, ``ImportedScholar`` or archive row depends on a row this
migration removes.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0077_last_mail_attempt'),
    ]

    operations = [
        # Dropped before the columns they name. The autodetector leaves these
        # out — it goes straight to RemoveField — and a constraint over a field
        # that no longer exists cannot be rebuilt, which is what SQLite does on
        # every table alteration.
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
