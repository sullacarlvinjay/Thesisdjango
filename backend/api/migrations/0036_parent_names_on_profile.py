from django.db import migrations, models


def split_combined(name):
    parts = (name or '').strip().split()
    if len(parts) >= 3:
        return parts[-1], parts[0], ' '.join(parts[1:-1])
    if len(parts) == 2:
        return parts[-1], parts[0], ''
    return (parts[0] if parts else ''), '', ''


def carry_names_over(apps, schema_editor):
    StudentProfile = apps.get_model('api', 'StudentProfile')
    TESApplication = apps.get_model('api', 'TESApplication')

    from_tes = {}
    for tes in TESApplication.objects.all().order_by('submitted_at'):
        from_tes[tes.student_id] = tes

    for profile in StudentProfile.objects.all():
        tes = from_tes.get(profile.id)
        changed = []

        if tes and (tes.father_last_name or tes.father_first_name):
            profile.father_last_name = tes.father_last_name
            profile.father_first_name = tes.father_first_name
            profile.father_middle_name = tes.father_middle_name
            changed.append('father')
        elif profile.father_name.strip():
            last, first, middle = split_combined(profile.father_name)
            profile.father_last_name, profile.father_first_name = last, first
            profile.father_middle_name = middle
            changed.append('father')

        if tes and (tes.mother_last_name or tes.mother_first_name):
            profile.mother_last_name = tes.mother_last_name
            profile.mother_first_name = tes.mother_first_name
            profile.mother_middle_name = tes.mother_middle_name
            changed.append('mother')
        elif profile.mother_name.strip():
            last, first, middle = split_combined(profile.mother_name)
            profile.mother_last_name, profile.mother_first_name = last, first
            profile.mother_middle_name = middle
            changed.append('mother')

        if tes and tes.middle_name.strip() and not profile.middle_name.strip():
            profile.middle_name = tes.middle_name
            changed.append('middle_name')

        if changed:
            profile.save()


def put_names_back(apps, schema_editor):
    StudentProfile = apps.get_model('api', 'StudentProfile')
    for profile in StudentProfile.objects.all():
        def joined(last, first, middle):
            initial = f'{middle.strip()[0].upper()}.' if middle.strip() else ''
            return ' '.join(p for p in (first.strip(), initial, last.strip()) if p)
        profile.father_name = joined(profile.father_last_name, profile.father_first_name,
                                     profile.father_middle_name)
        profile.mother_name = joined(profile.mother_last_name, profile.mother_first_name,
                                     profile.mother_middle_name)
        profile.save(update_fields=['father_name', 'mother_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0035_tes_eligibility_fields'),
    ]

    operations = [
        migrations.AddField('studentprofile', 'father_last_name',
                            models.CharField(blank=True, max_length=100)),
        migrations.AddField('studentprofile', 'father_first_name',
                            models.CharField(blank=True, max_length=100)),
        migrations.AddField('studentprofile', 'father_middle_name',
                            models.CharField(blank=True, max_length=100)),
        migrations.AddField('studentprofile', 'mother_last_name',
                            models.CharField(blank=True, max_length=100)),
        migrations.AddField('studentprofile', 'mother_first_name',
                            models.CharField(blank=True, max_length=100)),
        migrations.AddField('studentprofile', 'mother_middle_name',
                            models.CharField(blank=True, max_length=100)),

        migrations.RunPython(carry_names_over, put_names_back),

        migrations.RemoveField('studentprofile', 'father_name'),
        migrations.RemoveField('studentprofile', 'mother_name'),
        migrations.RemoveField('tesapplication', 'middle_name'),
        migrations.RemoveField('tesapplication', 'father_last_name'),
        migrations.RemoveField('tesapplication', 'father_first_name'),
        migrations.RemoveField('tesapplication', 'father_middle_name'),
        migrations.RemoveField('tesapplication', 'mother_last_name'),
        migrations.RemoveField('tesapplication', 'mother_first_name'),
        migrations.RemoveField('tesapplication', 'mother_middle_name'),
    ]
