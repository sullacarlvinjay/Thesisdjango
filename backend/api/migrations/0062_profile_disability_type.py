"""Ask which disability instead of whether there is one, and carry the answer over.

``is_pwd`` was a checkbox on the socio-economic row. The same student was also
asked, on the TES form, to name their disability from CHED's own list — so the
system held two answers to one question and nothing kept them in step. The
question is now asked once, in the shape CHED asks it, and ``is_pwd`` is read
back off it (see ``StudentProfile.is_pwd``).

What a ticked box carried across:

* the disability already named on that student's TES application, when there is
  one — that is the better record of the two, and the only one that says which;
* otherwise 'Unspecified Disability'. It records the declaration without
  inventing a condition to go with it, and reads as PWD everywhere is_pwd is
  read. The profile form shows it under 'Other', where the student can replace
  it with the real one.

An unticked box carries nothing: blank already means 'no disability recorded',
which is what False meant.
"""
from django.db import migrations, models

UNSPECIFIED = 'Unspecified Disability'

# What a TESApplication.disability_type holds when the applicant declined the
# question. Copying one of these across would turn 'no' into a condition.
DECLINED = {'', 'n/a', 'na', 'n.a.', 'none', 'no', 'not applicable', 'wala', '-', '--', 'nil'}


def carry_pwd_onto_the_disability(apps, schema_editor):
    SocioEconomic = apps.get_model('api', 'SocioEconomicProfile')
    Personal = apps.get_model('api', 'PersonalInformation')
    TESApplication = apps.get_model('api', 'TESApplication')

    named = {}
    for tes in TESApplication.objects.all():
        value = (tes.disability_type or '').strip()
        if value.casefold() not in DECLINED:
            named.setdefault(tes.student_id, value)

    pwd_students = set(
        SocioEconomic.objects.filter(is_pwd=True).values_list('student_id', flat=True))
    if not pwd_students:
        return

    rows = list(Personal.objects.filter(student_id__in=pwd_students))
    for row in rows:
        row.disability_type = named.get(row.student_id, UNSPECIFIED)
    Personal.objects.bulk_update(rows, ['disability_type'])

    # A student whose personal row was never written still has to keep the flag.
    missing = pwd_students - {row.student_id for row in rows}
    Personal.objects.bulk_create([
        Personal(student_id=student_id,
                 disability_type=named.get(student_id, UNSPECIFIED))
        for student_id in missing
    ])


def carry_the_disability_back_onto_pwd(apps, schema_editor):
    SocioEconomic = apps.get_model('api', 'SocioEconomicProfile')
    Personal = apps.get_model('api', 'PersonalInformation')

    with_one = [
        row.student_id for row in Personal.objects.all()
        if (row.disability_type or '').strip().casefold() not in DECLINED
    ]
    SocioEconomic.objects.filter(student_id__in=with_one).update(is_pwd=True)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0061_drop_endorsed_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='personalinformation',
            name='disability_type',
            field=models.CharField(blank=True, help_text="A value from CHED's Disability_List, or 'NO' for none.", max_length=100),
        ),
        migrations.RunPython(carry_pwd_onto_the_disability,
                             carry_the_disability_back_onto_pwd),
    ]
