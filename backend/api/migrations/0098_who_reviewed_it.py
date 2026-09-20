import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def retire_the_super_role(apps, schema_editor):
    """Leave no account on a role the portal no longer answers to.

    ``super`` was mapped to a portal path that was never routed, so an account
    holding it signed in and landed nowhere, while still counting as the office
    to the API and to the document store. Such an account becomes an office
    account that cannot sign in, which is the state a person can look at and
    decide about, rather than one that silently half-works.
    """
    apps.get_model('api', 'User').objects.filter(role='super').update(
        role='vpsea', is_active=False)


def restore_the_super_role(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0097_office_mfa'),
    ]

    operations = [
        migrations.AddField(
            model_name='academicrenewal',
            name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_academic_renewals', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='applicantrecord',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='applicantrecord',
            name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_applicant_records', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='application',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='application',
            name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_applications', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(retire_the_super_role, restore_the_super_role),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('student', 'Student'), ('nsu_staff', 'BiPSU Staff'), ('vpsea', 'VPSEA Admin'), ('partner', 'External Partner')], default='student', max_length=20),
        ),
    ]
