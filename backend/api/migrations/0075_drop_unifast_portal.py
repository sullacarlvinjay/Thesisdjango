"""Delete the UniFAST portal and the TES application, keeping the recommender.

**This drops data and cannot be undone.** BiPSU no longer administers TES here,
so everything the office had a screen for goes with it: the applications
students filed, the billing the office claimed from CHED, the liquidation that
answered for the money, and the cheques it was paid out on.

Two things deliberately survive.

**The scholarship programmes.** TES, TDP, SUC-TDP and FHE stay in the catalogue
and on the landing page — the university offers them, so saying so is still
true — and any award already recorded against one is an ordinary Application
row the masterlist and the archives go on reading.

**The recommender.** ``TESEligibility`` is not dropped. The rules in
api/tes_ranking.py move to the SDSO, which is the office that now says who it
would put forward for TES, so the answers those rules are checked against are
still collected — at registration and on My Profile, as before.

One column is added rather than removed: ``is_solo_parent_dependent`` was a
field on the TES application form and is a Priority 1 marker the rules read, so
it moves onto the student's own record with its neighbours. It is nullable here
where the form's version defaulted to False — a group nobody asked about is not
a group the student was found not to be in — and the answers already given on a
TES application are carried across before the table goes.

Two columns keep values the new choice lists no longer name, so both are
rewritten in the same pass:

* ``User.role`` of 'unifast'. The account has no portal to reach any more, so
  it is deactivated rather than deleted — its announcements and activity log
  entries are part of the office's record, and deleting the user would take
  them with it.
* ``Application.source`` of 'tes_application'. Those awards were filed by a
  student on a form in this portal, which is what 'portal' means, so that is
  what they become.
"""

from django.db import migrations, models


def retire_the_portal(apps, schema_editor):
    """Carry across what the recommender still needs, then close the office.

    Runs after ``is_solo_parent_dependent`` exists and before the TES tables go,
    which is the only window in which both sides of the copy are readable.
    """
    TESApplication = apps.get_model('api', 'TESApplication')
    TESEligibility = apps.get_model('api', 'TESEligibility')

    # One answer per student, newest first — a student could correct a pending
    # application, and the latest is the one they stood behind.
    answered = {}
    for app in TESApplication.objects.order_by('submitted_at'):
        answered[app.student_id] = app.is_solo_parent_dependent
    for student_id, value in answered.items():
        # Only where the student has a row to write it onto. Creating one here
        # would invent a record for a student who never had these fields.
        TESEligibility.objects.filter(student_id=student_id).update(
            is_solo_parent_dependent=value)

    apps.get_model('api', 'User').objects.filter(role='unifast').update(
        role='vpsea', is_active=False)
    apps.get_model('api', 'Application').objects.filter(
        source='tes_application').update(source='portal')


def reopen_the_portal(apps, schema_editor):
    """Nothing to restore. The reverse exists so the migration is reversible.

    Which account was UniFAST's is not recorded anywhere after the forward run,
    and the awards cannot be told apart from portal ones either — the table that
    would have said so is gone. Reversing this migration gets the schema back,
    never the data.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0074_partner_application_forms'),
    ]

    operations = [
        # The new column first: the data step below reads the old form's answers
        # into it while both still exist.
        migrations.AddField(
            model_name='teseligibility',
            name='is_solo_parent_dependent',
            field=models.BooleanField(blank=True, help_text='Dependent of a solo parent on the DSWD registry. Null means not yet asked.', null=True),
        ),
        migrations.RunPython(retire_the_portal, reopen_the_portal),
        # Application survives, so its foreign key goes before the table it
        # points at.
        migrations.RemoveField(
            model_name='application',
            name='tes_application',
        ),
        migrations.AlterField(
            model_name='application',
            name='source',
            field=models.CharField(choices=[('portal', 'Student portal'), ('link', 'Approved link request'), ('renewal', 'Approved renewal'), ('import', 'Office import')], db_index=True, default='portal', max_length=20),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('student', 'Student'), ('nsu_staff', 'BiPSU Staff'), ('vpsea', 'VPSEA Admin'), ('partner', 'External Partner'), ('super', 'Super Admin')], default='student', max_length=20),
        ),
        # Dropped whole, leaf tables first. Dropping the table takes its columns
        # and constraints with it — removing the columns one at a time first is
        # what SQLite cannot do here, because remaking TESDisbursement without
        # ``tes_application`` leaves its unique constraint naming a column that
        # is no longer there.
        migrations.DeleteModel(
            name='TESDisbursement',
        ),
        migrations.DeleteModel(
            name='TESCheckIssued',
        ),
        migrations.DeleteModel(
            name='TESLiquidation',
        ),
        migrations.DeleteModel(
            name='TESBilling',
        ),
        migrations.DeleteModel(
            name='TESApplication',
        ),
    ]
