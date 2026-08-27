"""Parent names move onto StudentProfile, in parts, and stop being duplicated.

StudentProfile held one combined string per parent while TESApplication held the
same names split into last / first / middle. Two records of one fact, in two
shapes, kept in step by nobody.

The parts win: CHED's TES form asks for them separately, and a combined name
cannot be split back reliably — "Maria Dela Cruz Santos" has no single correct
reading. So the columns are added to the profile, filled from whatever is
already on file, and only then are the old ones dropped.

Filling order matters. A TES application's split names are what the student
actually typed into those boxes, so they are trusted first. The combined
profile string is only parsed when there is nothing better, and it is parsed
conservatively: the last token is the surname, the first is the given name, and
anything between is the middle name. A two-word name yields no middle name
rather than a guessed one.

The student's own middle_name is treated the same way: TESApplication.middle_name
is copied onto the profile where the profile has none, then dropped.
"""
from django.db import migrations, models


def split_combined(name):
    """('First Middle Last') -> (last, first, middle). Blank parts when unclear."""
    parts = (name or '').strip().split()
    if len(parts) >= 3:
        return parts[-1], parts[0], ' '.join(parts[1:-1])
    if len(parts) == 2:
        return parts[-1], parts[0], ''
    return (parts[0] if parts else ''), '', ''


def carry_names_over(apps, schema_editor):
    StudentProfile = apps.get_model('api', 'StudentProfile')
    TESApplication = apps.get_model('api', 'TESApplication')

    # What the student typed on their TES form, keyed by profile.
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
    """Rebuild the combined strings so the old columns are not restored empty."""
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
        # 1. The new columns, before anything is read out of the old ones.
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

        # 2. Carry every name that exists onto the profile.
        migrations.RunPython(carry_names_over, put_names_back),

        # 3. Only now drop the duplicates.
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
