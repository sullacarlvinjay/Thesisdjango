from django.db import migrations, models

UNSPECIFIED = 'Unspecified Disability'

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
