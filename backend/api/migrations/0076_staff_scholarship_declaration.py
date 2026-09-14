import api.validators
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0075_drop_unifast_portal'),
    ]

    operations = [
        migrations.CreateModel(
            name='StaffScholarshipDeclaration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('term_label', models.CharField(blank=True, db_index=True, help_text="Term as '<yy>-<sem>', e.g. '26-1'.", max_length=20)),
                ('school_year', models.CharField(blank=True, db_index=True, help_text="Expanded school year, e.g. '2026-2027'.", max_length=20)),
                ('semester', models.CharField(blank=True, choices=[('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')], max_length=20)),
                ('proof_document', models.FileField(upload_to='staff_declarations/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg', 'webp', 'heic']), api.validators.MaxFileSize()])),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending', max_length=20)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('remarks', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('linked_application', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='api.affirmativestaffapplication')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_staff_declarations', to=settings.AUTH_USER_MODEL)),
                ('staff_user', models.ForeignKey(limit_choices_to={'role': 'nsu_staff'}, on_delete=django.db.models.deletion.CASCADE, related_name='staff_declarations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-submitted_at'],
            },
        ),
    ]
