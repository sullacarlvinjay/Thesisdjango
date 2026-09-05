"""Build the detail tables the staff record and its applications split onto.

Three migrations do the split, in the only order that keeps the data: this one
adds the tables, 0058 copies the columns into them, and 0059 drops the columns
that have been copied. A single migration would drop the source columns in the
same transaction that created their replacements.

The same shape 0049-0051 used for the student record, for the same reason.
"""

import api.validators
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0056_tes_billing'),
    ]

    operations = [
        # Three columns were declared without blank=True or a default, so a
        # reversal has no value to give the rows already in the table and fails
        # on the NOT NULL constraint. They are softened here, before 0058 copies
        # them across, rather than beside the drops in 0059: reversing replays
        # 0059, then 0058, then this, so the tightening has to be the last step
        # back or it meets a column 0058's reverse has not filled yet.
        migrations.AlterField(
            model_name='affirmativestaffapplication',
            name='contact_number',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name='affirmativestaffapplication',
            name='course',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='affirmativestaffapplication',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ApplicantAffirmativeEligibility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shs_gpa', models.FloatField(blank=True, null=True)),
                ('shs_certificate', models.FileField(blank=True, null=True, upload_to='affirmative/shs/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg', 'webp', 'heic']), api.validators.MaxFileSize()])),
                ('suc_exam_score', models.FloatField(blank=True, help_text='Raw score. A percentage when suc_exam_total is blank.', null=True)),
                ('suc_exam_total', models.FloatField(blank=True, help_text='Items the exam was out of. Blank means the score is already a percentage.', null=True)),
                ('suc_exam_certificate', models.FileField(blank=True, null=True, upload_to='affirmative/suc/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg', 'webp', 'heic']), api.validators.MaxFileSize()])),
                ('is_tes_beneficiary', models.BooleanField(default=False)),
                ('application', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='affirmative_eligibility', to='api.affirmativestaffapplication')),
            ],
            options={
                'verbose_name': 'applicant affirmative eligibility',
                'verbose_name_plural': 'applicant affirmative eligibility',
            },
        ),
        migrations.CreateModel(
            name='ApplicantEmployment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('employment_status', models.CharField(blank=True, choices=[('Regular', 'Regular'), ('Contractual', 'Contractual'), ('Part-time', 'Part-time')], max_length=30)),
                ('designation', models.CharField(blank=True, choices=[('Teaching', 'Teaching'), ('Non-Teaching', 'Non-Teaching')], max_length=30)),
                ('department', models.CharField(blank=True, max_length=200)),
                ('position', models.CharField(blank=True, max_length=200)),
                ('years_of_service', models.IntegerField(blank=True, null=True)),
                ('date_of_regularization', models.DateField(blank=True, null=True)),
                ('appointment_paper', models.FileField(blank=True, null=True, upload_to='staff/appointment/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg', 'webp', 'heic']), api.validators.MaxFileSize()])),
                ('application', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='employment', to='api.affirmativestaffapplication')),
            ],
            options={
                'verbose_name': 'applicant employment',
                'verbose_name_plural': 'applicant employment',
            },
        ),
        migrations.CreateModel(
            name='ApplicantEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school', models.CharField(blank=True, max_length=100)),
                ('course', models.CharField(blank=True, max_length=100)),
                ('year_level', models.IntegerField(default=1)),
                ('student_id', models.CharField(blank=True, max_length=30)),
                ('application', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='enrollment', to='api.affirmativestaffapplication')),
            ],
            options={
                'verbose_name': 'applicant enrollment',
                'verbose_name_plural': 'applicant enrollment',
            },
        ),
        migrations.CreateModel(
            name='ApplicantInformation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contact_number', models.CharField(blank=True, max_length=20)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('gender', models.CharField(blank=True, choices=[('Male', 'Male'), ('Female', 'Female')], max_length=10)),
                ('application', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='applicant', to='api.affirmativestaffapplication')),
            ],
            options={
                'verbose_name': 'applicant information',
                'verbose_name_plural': 'applicant information',
            },
        ),
        migrations.CreateModel(
            name='ApplicantStaffEligibility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_nsu_staff', models.BooleanField(default=False)),
                ('is_nsu_dependent', models.BooleanField(default=False)),
                ('staff_name', models.CharField(blank=True, max_length=200)),
                ('staff_employee_id', models.CharField(blank=True, max_length=50)),
                ('relationship_to_staff', models.CharField(blank=True, max_length=50)),
                ('has_baccalaureate', models.BooleanField(default=False)),
                ('application', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='staff_eligibility', to='api.affirmativestaffapplication')),
            ],
            options={
                'verbose_name': 'applicant staff eligibility',
                'verbose_name_plural': 'applicant staff eligibility',
            },
        ),
        migrations.CreateModel(
            name='StaffEducation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('highest_education', models.CharField(blank=True, max_length=200)),
                ('has_baccalaureate', models.BooleanField(default=False)),
                ('staff', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='education', to='api.staffprofile')),
            ],
            options={
                'verbose_name': 'staff education',
                'verbose_name_plural': 'staff education',
            },
        ),
        migrations.CreateModel(
            name='StaffEmployment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school', models.CharField(blank=True, choices=[('School of Technologies and Computer Studies', 'School of Technologies and Computer Studies'), ('School of Engineering', 'School of Engineering'), ('School of Nursing and Health Sciences', 'School of Nursing and Health Sciences'), ('School of Criminal Justice Education', 'School of Criminal Justice Education'), ('School of Tourism and Hospitality Management', 'School of Tourism and Hospitality Management'), ('School of Arts and Sciences', 'School of Arts and Sciences'), ('School of Teacher Education', 'School of Teacher Education'), ('School of Business and Management', 'School of Business and Management')], max_length=100)),
                ('department', models.CharField(blank=True, max_length=200)),
                ('position', models.CharField(blank=True, max_length=200)),
                ('employment_status', models.CharField(blank=True, choices=[('Regular', 'Regular'), ('Contractual', 'Contractual'), ('Part-time', 'Part-time')], max_length=30)),
                ('designation', models.CharField(blank=True, choices=[('Teaching', 'Teaching'), ('Non-Teaching', 'Non-Teaching')], max_length=30)),
                ('date_hired', models.DateField(blank=True, null=True)),
                ('date_of_regularization', models.DateField(blank=True, null=True)),
                ('declared_years_of_service', models.IntegerField(blank=True, help_text='Only read when date_hired is blank — see StaffProfile.years_of_service.', null=True)),
                ('appointment_paper', models.FileField(blank=True, null=True, upload_to='staff/appointment/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg', 'webp', 'heic']), api.validators.MaxFileSize()])),
                ('is_active', models.BooleanField(default=True)),
                ('separated_on', models.DateField(blank=True, null=True)),
                ('staff', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='employment', to='api.staffprofile')),
            ],
            options={
                'verbose_name': 'staff employment',
                'verbose_name_plural': 'staff employment',
            },
        ),
        migrations.CreateModel(
            name='StaffPersonalInformation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('middle_name', models.CharField(blank=True, max_length=100)),
                ('suffix', models.CharField(blank=True, help_text='Jr., Sr., III …', max_length=20)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('gender', models.CharField(blank=True, choices=[('Male', 'Male'), ('Female', 'Female')], max_length=10)),
                ('civil_status', models.CharField(blank=True, choices=[('Single', 'Single'), ('Married', 'Married'), ('Widowed', 'Widowed'), ('Separated', 'Separated')], max_length=20)),
                ('contact_number', models.CharField(blank=True, max_length=20)),
                ('staff', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='personal', to='api.staffprofile')),
            ],
            options={
                'verbose_name': 'staff personal information',
                'verbose_name_plural': 'staff personal information',
            },
        ),
    ]
