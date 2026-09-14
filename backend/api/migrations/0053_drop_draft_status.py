from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0052_scholarship_table_columns'),
    ]

    operations = [
        migrations.RunPython(
            lambda apps, schema_editor: [
                apps.get_model('api', name).objects
                .filter(status='Draft').update(status='Pending Validation')
                for name in ('Application', 'AffirmativeStaffApplication')
            ] and None,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='affirmativestaffapplication',
            name='status',
            field=models.CharField(choices=[('Pending Validation', 'Pending Validation'), ('Approved', 'Approved'), ('Rejected', 'Rejected'), ('Needs Revision', 'Needs Revision')], default='Pending Validation', max_length=30),
        ),
        migrations.AlterField(
            model_name='application',
            name='status',
            field=models.CharField(choices=[('Pending Validation', 'Pending Validation'), ('Approved', 'Approved'), ('Rejected', 'Rejected'), ('Needs Revision', 'Needs Revision')], default='Pending Validation', max_length=30),
        ),
    ]
