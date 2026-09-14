from django.db import migrations


def _split_middle(full_name):
    parts = (full_name or '').strip().split()
    return ' '.join(parts[1:-1]) if len(parts) >= 3 else ''


def backfill(apps, schema_editor):
    User = apps.get_model('api', 'User')
    StaffProfile = apps.get_model('api', 'StaffProfile')
    AffirmativeNSUApplication = apps.get_model('api', 'AffirmativeNSUApplication')

    for user in User.objects.filter(role='nsu_staff'):
        if StaffProfile.objects.filter(user=user).exists():
            continue
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
    apps.get_model('api', 'StaffProfile').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0031_staff_profile'),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
