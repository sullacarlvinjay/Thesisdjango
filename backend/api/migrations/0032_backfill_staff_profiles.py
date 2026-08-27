"""Give every BiPSU Staff user a StaffProfile, filled from their application.

Before this, a staff member's employment details lived on whichever
AffirmativeNSUApplication they had submitted last, matched by email address.
This lifts the latest such record onto the new profile so nobody has to retype
what they already filed. The applications keep their copies — they are the
snapshot the VPSEA office reviewed and must not change.
"""
from django.db import migrations


def _split_middle(full_name):
    """Middle name out of a single 'First Middle Last' string, blank if unclear."""
    parts = (full_name or '').strip().split()
    return ' '.join(parts[1:-1]) if len(parts) >= 3 else ''


def backfill(apps, schema_editor):
    User = apps.get_model('api', 'User')
    StaffProfile = apps.get_model('api', 'StaffProfile')
    AffirmativeNSUApplication = apps.get_model('api', 'AffirmativeNSUApplication')

    for user in User.objects.filter(role='nsu_staff'):
        if StaffProfile.objects.filter(user=user).exists():
            continue
        # Latest wins, the same rule the staff portal used to read by. A
        # rejected application still carries correct employment details, so it
        # is worth reading when there is nothing better.
        app = (AffirmativeNSUApplication.objects
               .filter(email=user.email)
               .order_by('-submitted_at')
               .first())
        if app is None:
            StaffProfile.objects.create(user=user)
            continue
        StaffProfile.objects.create(
            user=user,
            middle_name=_split_middle(app.full_name),
            date_of_birth=app.date_of_birth,
            gender=app.gender,
            contact_number=app.contact_number,
            barangay=app.barangay,
            municipality=app.municipality,
            province=app.province,
            employee_id=app.student_id,
            school=app.school,
            department=app.department,
            position=app.position,
            employment_status=app.employment_status,
            designation=app.designation,
            date_of_regularization=app.date_of_regularization,
            declared_years_of_service=app.years_of_service,
            appointment_paper=app.appointment_paper,
            has_baccalaureate=app.has_baccalaureate,
        )


def unbackfill(apps, schema_editor):
    """Drop every profile, including any created after this ran — the details
    are still on the applications, which is where the old code reads them."""
    apps.get_model('api', 'StaffProfile').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0031_staff_profile'),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
