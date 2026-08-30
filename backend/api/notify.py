"""Telling an applicant what the office decided.

Every review screen ends the same way: a status changes and the person who
submitted it needs to hear about it. Before this module each screen just saved
the row, so approvals and rejections reached nobody — the portal's bell only
ever lit up for link requests and account verification, which were the two
places that had remembered to write a Notification by hand.

There is one entry point, :func:`decision`, and it does both halves: the in-app
Notification the portal reads, and the same wording by email. Keeping them in
one call is the point — two call sites cannot drift into telling a student
different things about the same decision.

Email is best-effort by design. A mail server that is down, slow or
misconfigured must never take the office's review screen with it, so every send
is wrapped and logged. The office's decision is already saved by the time we get
here; failing to announce it is not a reason to lose it.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# Which Notification.type badge a status deserves, and how to open the sentence.
_TONE = {
    'Approved': ('success', 'has been approved'),
    'Rejected': ('warning', 'was not approved'),
    'Needs Revision': ('warning', 'needs changes before it can be approved'),
    'Pending Validation': ('info', 'is being reviewed'),
    'Pending': ('info', 'is being reviewed'),
}


def _recipient(target):
    """(StudentProfile or None, email or '') for a profile, user, or address."""
    from .models import StudentProfile, User

    if isinstance(target, StudentProfile):
        return target, (target.user.email or '')
    if isinstance(target, User):
        return StudentProfile.objects.filter(user=target).first(), (target.email or '')
    if isinstance(target, str):
        return None, target.strip()
    return None, ''


def send_email(to, subject, body):
    """Send one plain-text message. Returns True if it left the process.

    Never raises: callers are review screens mid-save, and a mail failure is not
    their problem to handle.
    """
    if not to:
        return False
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
        return True
    except Exception:                                   # noqa: BLE001
        # Bad credentials, no network, a refused relay — all the same to us.
        logger.exception('Could not email %s: %s', to, subject)
        return False


def notify(target, title, body, tone='info', email=True):
    """Write the in-app notification and optionally email the same words.

    ``target`` may be a StudentProfile, a User, or a bare email address. A
    target with no StudentProfile — office staff, or an applicant the office
    added who has no portal account — still gets the email; there is simply no
    bell for it to land in, because Notification hangs off StudentProfile.

    Returns ``(notified_in_app, emailed)``.
    """
    from .models import Notification

    profile, address = _recipient(target)

    in_app = False
    if profile is not None:
        Notification.objects.create(
            student=profile, type=tone, title=title, body=body,
        )
        in_app = True

    emailed = send_email(address, f'[BiPSU SRMS] {title}', body) if email else False
    return in_app, emailed


def broadcast(title, body, tone='info'):
    """Put one announcement in every student's portal.

    Posting an announcement used to write the Announcement row and stop there.
    The row surfaced in exactly one place — the top three on the student
    dashboard — so a fourth announcement pushed the first off the only screen it
    ever appeared on, and nobody was told any of them existed.

    Written straight into Notification rather than emailed: this goes to the
    whole student body, and sending that many messages inside the request would
    hold the office's page open on SMTP for as long as it took. The bell is
    immediate and costs one bulk insert.

    Returns the number of students reached.
    """
    from .models import Notification, StudentProfile

    profiles = list(StudentProfile.objects.only('id'))
    Notification.objects.bulk_create([
        Notification(student=p, type=tone, title=title, body=body)
        for p in profiles
    ])
    return len(profiles)


def decision(target, subject, status, remarks='', detail='', link=''):
    """Announce a review outcome.

    ``subject`` names what was decided in the applicant's own words — "Your
    Academic Scholarship application", "Your TES application". ``detail`` is an
    optional extra sentence, and ``link`` a portal path such as
    ``/student/applications/`` which becomes a full URL when SITE_URL is set.
    """
    tone, phrase = _TONE.get(status, ('info', f'was marked {status}'))

    title = f'{subject} {phrase}'
    lines = [f'{title}.']
    if detail:
        lines.append(detail)
    if remarks:
        lines.append(f'Remarks from the office: {remarks}')
    if link and getattr(settings, 'SITE_URL', ''):
        lines.append(f'You can view the details here: {settings.SITE_URL}{link}')

    return notify(target, title, '\n\n'.join(lines), tone=tone)
