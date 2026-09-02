"""Drop the StudentProfile columns 0050 copied onto the detail rows.

Reversible only as far as the schema goes: reversing recreates empty columns,
and 0050's reverse copies the values back into them.
"""
import api.validators
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0050_move_student_record_onto_detail_rows'),
    ]

    operations = [
        # `course` was the one column declared without blank=True or a default,
        # so re-adding it on a reversal had no value to give the rows already in
        # the table and failed on the NOT NULL constraint. Softened first, the
        # drop reverses into an empty column that 0050's reverse then fills.
        migrations.AlterField(
            model_name='studentprofile',
            name='course',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='citizenship',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='civil_status',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='contact_number',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='course',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='date_of_birth',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='elementary',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='family_income',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='father_first_name',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='father_last_name',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='father_middle_name',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='father_occupation',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='gender',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='gwa',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='has_other_scholarship',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='has_previous_degree',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='highschool',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='household_size',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='indigenous_group',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='is_4ps_beneficiary',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='is_athlete',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='is_coconut_farmer_family',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='is_listahanan_household',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='is_pwd',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='is_tes_beneficiary',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='last_school',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='middle_name',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='mother_first_name',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='mother_last_name',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='mother_middle_name',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='mother_occupation',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='parent_employment',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='school',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='shs_gpa',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='shs_gpa_cert',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='suc_exam_cert',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='suc_exam_score',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='suc_exam_total',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='suffix',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='year_first_enrolled',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='year_level',
        ),
    ]
