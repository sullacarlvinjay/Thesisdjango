"""Build the student detail tables and stamp every submission with its term.

Three migrations do the split, in the only order that keeps the data: this one
adds the new tables and columns, 0050 copies the profile's columns into them and
fills in the terms, and 0051 drops the columns that have been copied. Splitting
it up is what makes the middle step possible — a single migration would drop the
source columns in the same transaction that created their replacements.
"""

import api.validators
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0048_suc_exam_total'),
    ]

    operations = [
        migrations.AddField(
            model_name='academicrenewal',
            name='school_year',
            field=models.CharField(blank=True, db_index=True, help_text="Expanded school year, e.g. '2026-2027'.", max_length=20),
        ),
        migrations.AddField(
            model_name='academicrenewal',
            name='semester',
            field=models.CharField(blank=True, choices=[('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')], max_length=20),
        ),
        migrations.AddField(
            model_name='academicrenewal',
            name='term_label',
            field=models.CharField(blank=True, db_index=True, help_text="Term as '<yy>-<sem>', e.g. '26-1'.", max_length=20),
        ),
        migrations.AddField(
            model_name='affirmativestaffapplication',
            name='school_year',
            field=models.CharField(blank=True, db_index=True, help_text="Expanded school year, e.g. '2026-2027'.", max_length=20),
        ),
        migrations.AddField(
            model_name='affirmativestaffapplication',
            name='semester',
            field=models.CharField(blank=True, choices=[('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')], max_length=20),
        ),
        migrations.AddField(
            model_name='affirmativestaffapplication',
            name='term_label',
            field=models.CharField(blank=True, db_index=True, help_text="Term as '<yy>-<sem>', e.g. '26-1'.", max_length=20),
        ),
        migrations.AddField(
            model_name='scholarshiplinkrequest',
            name='school_year',
            field=models.CharField(blank=True, db_index=True, help_text="Expanded school year, e.g. '2026-2027'.", max_length=20),
        ),
        migrations.AddField(
            model_name='scholarshiplinkrequest',
            name='semester',
            field=models.CharField(blank=True, choices=[('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')], max_length=20),
        ),
        migrations.AddField(
            model_name='staffrenewal',
            name='school_year',
            field=models.CharField(blank=True, db_index=True, help_text="Expanded school year, e.g. '2026-2027'.", max_length=20),
        ),
        migrations.AddField(
            model_name='staffrenewal',
            name='semester',
            field=models.CharField(blank=True, choices=[('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')], max_length=20),
        ),
        migrations.AddField(
            model_name='staffrenewal',
            name='term_label',
            field=models.CharField(blank=True, db_index=True, help_text="Term as '<yy>-<sem>', e.g. '26-1'.", max_length=20),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='school_year',
            field=models.CharField(blank=True, db_index=True, help_text="Expanded school year, e.g. '2026-2027'.", max_length=20),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='semester',
            field=models.CharField(blank=True, choices=[('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')], max_length=20),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='term_label',
            field=models.CharField(blank=True, db_index=True, help_text="Term as '<yy>-<sem>', e.g. '26-1'.", max_length=20),
        ),
        migrations.AddField(
            model_name='tesapplication',
            name='school_year',
            field=models.CharField(blank=True, db_index=True, help_text="Expanded school year, e.g. '2026-2027'.", max_length=20),
        ),
        migrations.AddField(
            model_name='tesapplication',
            name='semester',
            field=models.CharField(blank=True, choices=[('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')], max_length=20),
        ),
        migrations.AddField(
            model_name='tesapplication',
            name='term_label',
            field=models.CharField(blank=True, db_index=True, help_text="Term as '<yy>-<sem>', e.g. '26-1'.", max_length=20),
        ),
        migrations.AlterField(
            model_name='application',
            name='term_label',
            field=models.CharField(blank=True, db_index=True, help_text="Term as '<yy>-<sem>', e.g. '26-1'.", max_length=20),
        ),
        migrations.AlterField(
            model_name='scholarlistimport',
            name='school_year',
            field=models.CharField(blank=True, db_index=True, help_text="Expanded school year, e.g. '2026-2027'.", max_length=20),
        ),
        migrations.AlterField(
            model_name='scholarlistimport',
            name='semester',
            field=models.CharField(blank=True, choices=[('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')], max_length=20),
        ),
        migrations.AlterField(
            model_name='scholarlistimport',
            name='term_label',
            field=models.CharField(blank=True, db_index=True, help_text="Term as '<yy>-<sem>', e.g. '26-1'.", max_length=20),
        ),
        migrations.AlterField(
            model_name='scholarshiplinkrequest',
            name='term_label',
            field=models.CharField(blank=True, db_index=True, help_text="Term as '<yy>-<sem>', e.g. '26-1'.", max_length=20),
        ),
        migrations.AlterField(
            model_name='staffprofile',
            name='school',
            field=models.CharField(blank=True, choices=[('School of Technologies and Computer Studies', 'School of Technologies and Computer Studies'), ('School of Engineering', 'School of Engineering'), ('School of Nursing and Health Sciences', 'School of Nursing and Health Sciences'), ('School of Criminal Justice Education', 'School of Criminal Justice Education'), ('School of Tourism and Hospitality Management', 'School of Tourism and Hospitality Management'), ('School of Arts and Sciences', 'School of Arts and Sciences'), ('School of Teacher Education', 'School of Teacher Education'), ('School of Business and Management', 'School of Business and Management')], max_length=100),
        ),
        migrations.CreateModel(
            name='AffirmativeEligibility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shs_gpa', models.FloatField(blank=True, null=True)),
                ('shs_gpa_cert', models.FileField(blank=True, null=True, upload_to='profile/shs_cert/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg', 'webp', 'heic']), api.validators.MaxFileSize()])),
                ('suc_exam_score', models.FloatField(blank=True, help_text='Raw score. A percentage when suc_exam_total is blank.', null=True)),
                ('suc_exam_total', models.FloatField(blank=True, help_text='Items the exam was out of. Blank means the score is already a percentage.', null=True)),
                ('suc_exam_cert', models.FileField(blank=True, null=True, upload_to='profile/suc_cert/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg', 'webp', 'heic']), api.validators.MaxFileSize()])),
                ('is_tes_beneficiary', models.BooleanField(default=False)),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='affirmative_eligibility', to='api.studentprofile')),
            ],
            options={
                'verbose_name': 'affirmative eligibility',
                'verbose_name_plural': 'affirmative eligibility',
            },
        ),
        migrations.CreateModel(
            name='EducationalBackground',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('elementary', models.CharField(blank=True, max_length=200)),
                ('highschool', models.CharField(blank=True, max_length=200)),
                ('last_school', models.CharField(blank=True, max_length=200)),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='education', to='api.studentprofile')),
            ],
            options={
                'verbose_name': 'educational background',
                'verbose_name_plural': 'educational backgrounds',
            },
        ),
        migrations.CreateModel(
            name='EnrollmentData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school', models.CharField(blank=True, max_length=100)),
                ('course', models.CharField(blank=True, max_length=100)),
                ('level', models.CharField(blank=True, choices=[('Undergraduate', 'Undergraduate'), ('Graduate', 'Graduate'), ('Post-Graduate', 'Post-Graduate')], help_text='Undergraduate, Graduate …', max_length=20)),
                ('department', models.CharField(blank=True, max_length=200)),
                ('curriculum', models.CharField(blank=True, help_text='Curriculum year the student is following, e.g. 2018-2019.', max_length=100)),
                ('year_level', models.IntegerField(default=1)),
                ('learner_ref_no', models.CharField(blank=True, db_index=True, help_text="DepEd Learner Reference Number (LRN), the student's ID from basic education.", max_length=30)),
                ('entry_period', models.CharField(blank=True, choices=[('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')], help_text='Semester the student first entered BiPSU.', max_length=20)),
                ('entry_date', models.DateField(blank=True, help_text='Date of first entry, as the registrar recorded it.', null=True)),
                ('exam_score', models.FloatField(blank=True, help_text="Admission exam score on the registrar's record. The score a scholarship is judged on is the certified one the student submits — see AffirmativeEligibility.suc_exam_score.", null=True)),
                ('gwa', models.FloatField(default=0.0)),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='enrollment', to='api.studentprofile')),
            ],
            options={
                'verbose_name': 'enrollment data',
                'verbose_name_plural': 'enrollment data',
            },
        ),
        migrations.CreateModel(
            name='FamilyBackground',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('father_last_name', models.CharField(blank=True, max_length=100)),
                ('father_first_name', models.CharField(blank=True, max_length=100)),
                ('father_middle_name', models.CharField(blank=True, max_length=100)),
                ('father_occupation', models.CharField(blank=True, max_length=200)),
                ('mother_last_name', models.CharField(blank=True, max_length=100)),
                ('mother_first_name', models.CharField(blank=True, max_length=100)),
                ('mother_middle_name', models.CharField(blank=True, max_length=100)),
                ('mother_occupation', models.CharField(blank=True, max_length=200)),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='family', to='api.studentprofile')),
            ],
            options={
                'verbose_name': 'family background',
                'verbose_name_plural': 'family backgrounds',
            },
        ),
        migrations.CreateModel(
            name='PersonalInformation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('middle_name', models.CharField(blank=True, max_length=100)),
                ('suffix', models.CharField(blank=True, help_text='Jr., Sr., III …', max_length=20)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('gender', models.CharField(blank=True, choices=[('Male', 'Male'), ('Female', 'Female')], max_length=10)),
                ('civil_status', models.CharField(blank=True, choices=[('Single', 'Single'), ('Married', 'Married'), ('Widowed', 'Widowed'), ('Separated', 'Separated')], max_length=20)),
                ('contact_number', models.CharField(blank=True, max_length=20)),
                ('birth_place', models.CharField(blank=True, max_length=200)),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='personal', to='api.studentprofile')),
            ],
            options={
                'verbose_name': 'personal information',
                'verbose_name_plural': 'personal information',
            },
        ),
        migrations.CreateModel(
            name='SocioEconomicProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('family_income', models.FloatField(default=0.0)),
                ('household_size', models.IntegerField(blank=True, null=True)),
                ('indigenous_group', models.CharField(blank=True, max_length=100)),
                ('parent_employment', models.CharField(blank=True, max_length=100)),
                ('is_pwd', models.BooleanField(default=False)),
                ('is_athlete', models.BooleanField(default=False)),
                ('is_coconut_farmer_family', models.BooleanField(default=False)),
                ('has_other_scholarship', models.BooleanField(default=False)),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='socioeconomic', to='api.studentprofile')),
            ],
            options={
                'verbose_name': 'socio-economic profile',
                'verbose_name_plural': 'socio-economic profiles',
            },
        ),
        migrations.CreateModel(
            name='TESEligibility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('citizenship', models.CharField(blank=True, help_text="Blank means not yet recorded, not 'non-Filipino'.", max_length=50)),
                ('is_listahanan_household', models.BooleanField(blank=True, help_text='DSWD Listahanan listing. Null means not yet checked against the list.', null=True)),
                ('is_4ps_beneficiary', models.BooleanField(blank=True, help_text='Pantawid Pamilyang Pilipino Program. Stands in for Listahanan when that list is unavailable.', null=True)),
                ('has_previous_degree', models.BooleanField(blank=True, help_text='Holds an earlier undergraduate degree. Null means unknown.', null=True)),
                ('year_first_enrolled', models.IntegerField(blank=True, help_text='Calendar year the student first enrolled in this programme, for the maximum-years rule.', null=True)),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='tes_eligibility', to='api.studentprofile')),
            ],
            options={
                'verbose_name': 'TES eligibility',
                'verbose_name_plural': 'TES eligibility',
            },
        ),
    ]
