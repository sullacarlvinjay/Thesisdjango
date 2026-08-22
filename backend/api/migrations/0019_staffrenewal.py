from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0018_user_nsu_staff_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='StaffRenewal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('certificate_of_grades', models.FileField(upload_to='renewals/staff/')),
                ('certificate_of_enrollment', models.FileField(upload_to='renewals/staff/')),
                ('supporting_document', models.FileField(blank=True, null=True, upload_to='renewals/staff/')),
                ('status', models.CharField(
                    choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')],
                    default='Pending',
                    max_length=20,
                )),
                ('remarks', models.TextField(blank=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('staff_user', models.ForeignKey(
                    limit_choices_to={'role': 'nsu_staff'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='staff_renewals',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-submitted_at']},
        ),
    ]
