from django.db import migrations


def nsu_staff_to_staff(apps, schema_editor):
    """'NSU Staff' and 'Staff' were the same BiPSU program stored under two keys.

    'NSU Staff' came from the old student-portal staff flow, which now lives in
    the dedicated NSU Staff portal. 'Staff' is the canonical key used by
    Scholarship.type, the archives and the reports, so collapse onto it.
    """
    for model, field in (
        ('ScholarshipLinkRequest', 'scholarship_type'),
        ('ArchiveRecord', 'scholarship_type'),
        ('Scholarship', 'type'),
    ):
        apps.get_model('api', model).objects.filter(
            **{field: 'NSU Staff'}
        ).update(**{field: 'Staff'})


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0021_link_request_review_and_archive_claim'),
    ]

    operations = [
        migrations.RunPython(nsu_staff_to_staff, migrations.RunPython.noop),
    ]
