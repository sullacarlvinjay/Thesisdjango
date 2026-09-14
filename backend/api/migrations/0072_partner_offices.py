import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0071_scholarship_application_window'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('student', 'Student'), ('nsu_staff', 'BiPSU Staff'), ('vpsea', 'VPSEA Admin'), ('unifast', 'UniFAST Admin'), ('partner', 'External Partner'), ('super', 'Super Admin')], default='student', max_length=20),
        ),
        migrations.CreateModel(
            name='PartnerOffice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('logo', models.CharField(blank=True, help_text="Seal filename from media/logos/. Blank uses BiPSU's.", max_length=100)),
                ('may_add_scholarships', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('scholarships', models.ManyToManyField(blank=True, help_text='Programmes this partner may see. None means they see nothing.', related_name='partner_offices', to='api.scholarship')),
            ],
            options={
                'verbose_name': 'partner office',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='user',
            name='partner_office',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='accounts', to='api.partneroffice'),
        ),
    ]
