"""Copy every staff record and staff application onto their detail rows.

Runs between 0057, which builds the tables, and 0059, which drops the columns
read here. A row is written for every record and every group, even an empty one,
for the reason 0050 gives for the student side: a profile reads a missing row as
"the default a fresh one would hold", which is right, but leaving some records
short of a row would mean the admin inlines and any query against a detail table
saw a different population than the parent table does. ``ensure_details`` on
:class:`~api.models.DetailRows` does the same for every record created after
this.
"""
from django.db import migrations

# parent model -> related name -> (detail model, the columns to carry across)
DETAIL_GROUPS = {
    'StaffProfile': {
        'employment': ('StaffEmployment', [
            'school', 'department', 'position', 'employment_status',
            'designation', 'date_hired', 'date_of_regularization',
            'declared_years_of_service', 'appointment_paper', 'is_active',
            'separated_on']),
        'personal': ('StaffPersonalInformation', [
            'middle_name', 'suffix', 'date_of_birth', 'gender', 'civil_status',
            'contact_number']),
        'education': ('StaffEducation', ['highest_education', 'has_baccalaureate']),
    },
    'AffirmativeStaffApplication': {
        'applicant': ('ApplicantInformation', [
            'contact_number', 'date_of_birth', 'gender']),
        'enrollment': ('ApplicantEnrollment', [
            'school', 'course', 'year_level', 'student_id']),
        'staff_eligibility': ('ApplicantStaffEligibility', [
            'is_nsu_staff', 'is_nsu_dependent', 'staff_name',
            'staff_employee_id', 'relationship_to_staff', 'has_baccalaureate']),
        'employment': ('ApplicantEmployment', [
            'employment_status', 'designation', 'department', 'position',
            'years_of_service', 'date_of_regularization', 'appointment_paper']),
        'affirmative_eligibility': ('ApplicantAffirmativeEligibility', [
            'shs_gpa', 'shs_certificate', 'suc_exam_score', 'suc_exam_total',
            'suc_exam_certificate', 'is_tes_beneficiary']),
    },
}

# The column on each detail table that points back at its parent.
DETAIL_LINK = {
    'StaffProfile': 'staff',
    'AffirmativeStaffApplication': 'application',
}


def move_forward(apps, schema_editor):
    for parent_name, groups in DETAIL_GROUPS.items():
        Parent = apps.get_model('api', parent_name)
        link = DETAIL_LINK[parent_name]
        parents = list(Parent.objects.all())
        for related, (model_name, columns) in groups.items():
            Detail = apps.get_model('api', model_name)
            Detail.objects.bulk_create([
                Detail(**dict(
                    {link: parent},
                    **{c: getattr(parent, c) for c in columns}
                ))
                for parent in parents
            ], batch_size=500)


def move_backward(apps, schema_editor):
    """Copy the detail rows back onto their parent, for a reversal of 0059."""
    for parent_name, groups in DETAIL_GROUPS.items():
        Parent = apps.get_model('api', parent_name)
        link = DETAIL_LINK[parent_name]
        for related, (model_name, columns) in groups.items():
            Detail = apps.get_model('api', model_name)
            parents = []
            for row in Detail.objects.select_related(link):
                parent = getattr(row, link)
                for column in columns:
                    setattr(parent, column, getattr(row, column))
                parents.append(parent)
            if parents:
                Parent.objects.bulk_update(parents, columns, batch_size=500)
            Detail.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0057_staff_detail_tables'),
    ]

    operations = [
        migrations.RunPython(move_forward, move_backward),
    ]
