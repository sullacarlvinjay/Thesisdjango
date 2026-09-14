from django.db import migrations, models


def retire_the_portal(apps, schema_editor):
    TESApplication = apps.get_model('api', 'TESApplication')
    TESEligibility = apps.get_model('api', 'TESEligibility')

    answered = {}
    for app in TESApplication.objects.order_by('submitted_at'):
        answered[app.student_id] = app.is_solo_parent_dependent
    for student_id, value in answered.items():
        TESEligibility.objects.filter(student_id=student_id).update(
            is_solo_parent_dependent=value)

    apps.get_model('api', 'User').objects.filter(role='unifast').update(
        role='vpsea', is_active=False)
    apps.get_model('api', 'Application').objects.filter(
        source='tes_application').update(source='portal')


def reopen_the_portal(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0074_partner_application_forms'),
    ]

    operations = [
        migrations.AddField(
            model_name='teseligibility',
            name='is_solo_parent_dependent',
            field=models.BooleanField(blank=True, help_text='Dependent of a solo parent on the DSWD registry. Null means not yet asked.', null=True),
        ),
        migrations.RunPython(retire_the_portal, reopen_the_portal),
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
