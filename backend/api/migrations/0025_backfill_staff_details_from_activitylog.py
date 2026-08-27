import re

from django.db import migrations


# Staff registrations used to dump these four values into a single free-text
# ActivityLog line, which nothing could read back. Recover them into the real
# User columns added in 0024.
LOG_PATTERN = re.compile(
    r'Employee ID:\s*(?P<employee_id>.*?)\s*\|\s*'
    r'Department:\s*(?P<department>.*?)\s*\|\s*'
    r'Position:\s*(?P<position>.*?)\s*\|\s*'
    r'Contact:\s*(?P<contact_number>.*?)\s*$'
)


def _clean(value):
    """The old format wrote an em dash for missing values; treat those as blank.

    The dash also survives in mojibake form in some rows, so anything without a
    letter or digit counts as empty rather than trying to match it literally.
    """
    value = (value or '').strip()
    return value if any(ch.isalnum() for ch in value) else ''


def backfill(apps, schema_editor):
    User = apps.get_model('api', 'User')
    ActivityLog = apps.get_model('api', 'ActivityLog')

    logs = ActivityLog.objects.filter(
        action__startswith='Staff account created'
    ).order_by('created_at')

    for log in logs:
        if not log.user_id:
            continue
        match = LOG_PATTERN.search(log.action or '')
        if not match:
            continue
        user = User.objects.filter(pk=log.user_id).first()
        if not user:
            continue
        updated = []
        for field, value in match.groupdict().items():
            value = _clean(value)
            # Never clobber a value the staff member has since typed in.
            if value and not getattr(user, field, ''):
                setattr(user, field, value[:User._meta.get_field(field).max_length])
                updated.append(field)
        if updated:
            user.save(update_fields=updated)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0024_staff_details_on_user'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
