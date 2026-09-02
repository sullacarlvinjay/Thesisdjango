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


def notify(target, title, body, tone='info', email=True, email_body=None):
    """Write the in-app notification and optionally email the same words.

    ``target`` may be a StudentProfile, a User, or a bare email address. A
    target with no StudentProfile — office staff, or an applicant the office
    added who has no portal account — still gets the email; there is simply no
    bell for it to land in, because Notification hangs off StudentProfile.

    ``email_body`` says it at more length for the message that leaves the
    building. The bell sits inside a portal that gives it all its context — who
    it is about, what it refers to, a link to the thing. An email arrives with
    none of that, sometimes to someone who cannot sign in to go and look, so a
    one-line body that reads perfectly in the portal can be unreadable in an
    inbox. Both still come from this one call, so they cannot contradict.

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

    emailed = send_email(
        address, f'[BiPSU SRMS] {title}', email_body or body) if email else False
    return in_app, emailed


def account_decision(account, status, note):
    """Tell someone whether their registration was accepted, and what happens next.

    Its own function because this message goes to a person who, half the time,
    cannot sign in to read anything else — a rejected registration has no portal
    behind it. The office's own note is the heart of it; everything around it is
    the context an inbox does not supply.
    """
    approved = status == 'approved'
    title = 'Account verified' if approved else 'Account not verified'

    greeting = f'Hi {account.first_name},' if account.first_name else 'Hello,'
    opening = (
        'Your registration for the BiPSU Scholarship Records Management System '
        'has been verified by the Student Development and Services Office '
        '(SDSO). You can sign in now with the email and password you chose.'
        if approved else
        'The Student Development and Services Office (SDSO) has reviewed your '
        'registration for the BiPSU Scholarship Records Management System and '
        'could not verify it. Your account cannot be used to sign in yet.'
    )

    lines = [greeting, opening]
    if note:
        lines.append(f'From the office: {note}')
    if getattr(settings, 'SITE_URL', ''):
        lines.append(
            f'Sign in here: {settings.SITE_URL}/login/' if approved
            else f'{settings.SITE_URL}/login/ shows the same message '
                 'whenever you try to sign in.')
    if not approved:
        lines.append(
            'If you think this is a mistake, contact the SDSO office. Once the '
            'details check out they can verify the account, and the same email '
            'and password will get you in.')

    return notify(
        account, title, note,
        tone='success' if approved else 'warning',
        email_body='\n\n'.join(lines),
    )


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
