from django.db import migrations, models

RENAMED_APPOINTMENTS = {
    'Contractual': 'Contract of Service',
    'Part-time': 'Part Time',
}

EMPLOYMENT_TABLES = ('StaffEmployment', 'ApplicantEmployment')


def rename_forward(apps, schema_editor):
    for table in EMPLOYMENT_TABLES:
        Employment = apps.get_model('api', table)
        for old, new in RENAMED_APPOINTMENTS.items():
            (Employment.objects.filter(employment_status=old)
             .update(employment_status=new))


def rename_backward(apps, schema_editor):
    for table in EMPLOYMENT_TABLES:
        Employment = apps.get_model('api', table)
        for old, new in RENAMED_APPOINTMENTS.items():
            (Employment.objects.filter(employment_status=new)
             .update(employment_status=old))


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0089_applicant_record'),
    ]

    operations = [
        migrations.AlterField(
            model_name='applicantemployment',
            name='employment_status',
            field=models.CharField(blank=True, choices=[('Regular', 'Regular'), ('Contract of Service', 'Contract of Service'), ('Part Time', 'Part Time'), ('Job Order', 'Job Order')], max_length=30),
        ),
        migrations.AlterField(
            model_name='staffemployment',
            name='employment_status',
            field=models.CharField(blank=True, choices=[('Regular', 'Regular'), ('Contract of Service', 'Contract of Service'), ('Part Time', 'Part Time'), ('Job Order', 'Job Order')], max_length=30),
        ),
        migrations.RunPython(rename_forward, rename_backward),
    ]
