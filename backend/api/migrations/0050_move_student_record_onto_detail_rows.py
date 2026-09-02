"""Copy every student's record onto their detail rows, and stamp the terms.

Runs between 0049, which builds the tables, and 0051, which drops the columns
read here. A row is written for every student and every group, even an empty
one: the profile reads a missing row as "the default a fresh one would hold",
which is right, but leaving some students short of a row would mean the admin
inlines and any query against a detail table saw a different population than
the profile table does. StudentProfile.ensure_details does the same for every
student registered after this.

The term backfill uses each record's own submission date rather than the active
term, because these are historical submissions: a renewal filed in October 2025
belongs to the first semester of 2025-2026, not to whatever term happens to be
open when this migration runs.
"""
from django.db import migrations

# related name -> (detail model, the columns to carry across)
DETAIL_GROUPS = {
    'enrollment': ('EnrollmentData', ['school', 'course', 'year_level', 'gwa']),
    'personal': ('PersonalInformation', [
        'middle_name', 'suffix', 'date_of_birth', 'gender', 'civil_status',
        'contact_number']),
    'affirmative_eligibility': ('AffirmativeEligibility', [
        'shs_gpa', 'shs_gpa_cert', 'suc_exam_score', 'suc_exam_total',
        'suc_exam_cert', 'is_tes_beneficiary']),
    'socioeconomic': ('SocioEconomicProfile', [
        'family_income', 'household_size', 'indigenous_group',
        'parent_employment', 'is_pwd', 'is_athlete',
        'is_coconut_farmer_family', 'has_other_scholarship']),
    'tes_eligibility': ('TESEligibility', [
        'citizenship', 'is_listahanan_household', 'is_4ps_beneficiary',
        'has_previous_degree', 'year_first_enrolled']),
    'education': ('EducationalBackground', ['elementary', 'highschool', 'last_school']),
    'family': ('FamilyBackground', [
        'father_last_name', 'father_first_name', 'father_middle_name',
        'father_occupation', 'mother_last_name', 'mother_first_name',
        'mother_middle_name', 'mother_occupation']),
}

# The student-submitted records that gained a term stamp, and the date field the
# backfill reads a historical term off.
TERM_STAMPED = [
    # A profile has no date of its own; the account it belongs to was created
    # when the student registered, which is exactly the term being recorded.
    ('StudentProfile', 'user.date_joined'),
    ('AcademicRenewal', 'submitted_at'),
    ('StaffRenewal', 'submitted_at'),
    ('TESApplication', 'submitted_at'),
    ('AffirmativeStaffApplication', 'submitted_at'),
    ('ScholarshipLinkRequest', 'submitted_at'),
    ('ScholarListImport', 'created_at'),
]


def label_for(when):
    """The '<yy>-<sem>' term a date falls in.

    BiPSU's first semester runs from August; anything from January to July is
    the second semester of the school year that started the previous August.
    """
    if when is None:
        return ''
    year, month = when.year, when.month
    if month >= 8:
        return f'{year - 2000}-1'
    return f'{year - 1 - 2000}-2'


def submitted_on(row, path):
    """The date a row was submitted, following a dotted path across a relation."""
    for step in path.split('.'):
        row = getattr(row, step, None)
        if row is None:
            return None
    return row


def parse_label(label):
    try:
        yy, sem = label.split('-')
        start = 2000 + int(yy)
        return f'{start}-{start + 1}', ('1st Semester' if sem == '1' else '2nd Semester')
    except Exception:
        return label, '1st Semester'


def move_forward(apps, schema_editor):
    StudentProfile = apps.get_model('api', 'StudentProfile')
    for related, (model_name, columns) in DETAIL_GROUPS.items():
        Detail = apps.get_model('api', model_name)
        Detail.objects.bulk_create([
            Detail(student=profile, **{c: getattr(profile, c) for c in columns})
            for profile in StudentProfile.objects.all()
        ], batch_size=500)

    for model_name, date_field in TERM_STAMPED:
        Model = apps.get_model('api', model_name)
        rows = []
        for row in Model.objects.all():
            if row.term_label and row.school_year:
                continue
            if not row.term_label:
                row.term_label = label_for(submitted_on(row, date_field)) or row.school_year
            if row.term_label and not row.school_year:
                row.school_year, semester = parse_label(row.term_label)
                row.semester = row.semester or semester
            rows.append(row)
        if rows:
            Model.objects.bulk_update(
                rows, ['term_label', 'school_year', 'semester'], batch_size=500)


def move_backward(apps, schema_editor):
    """Copy the detail rows back onto the profile, for a reversal of 0051."""
    StudentProfile = apps.get_model('api', 'StudentProfile')
    for related, (model_name, columns) in DETAIL_GROUPS.items():
        Detail = apps.get_model('api', model_name)
        profiles = []
        for row in Detail.objects.select_related('student'):
            profile = row.student
            for column in columns:
                setattr(profile, column, getattr(row, column))
            profiles.append(profile)
        if profiles:
            StudentProfile.objects.bulk_update(profiles, columns, batch_size=500)
        Detail.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0049_student_detail_tables_and_term_columns'),
    ]

    operations = [
        migrations.RunPython(move_forward, move_backward),
    ]
