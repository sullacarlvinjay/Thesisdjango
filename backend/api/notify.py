"""Telling people things, in the portal and by email.

Two channels with different guarantees. The in-app notification is reliable and
is written first; the email is best-effort and its failure is swallowed
deliberately — every caller is doing something more important than the message,
and none should be rolled back because a mail server was briefly unreachable.

The outcome of the last attempt is recorded for the office's mail panel, which
on a deployment with no shell is the only way anyone finds out whether mail
works.

Mail leaves on the background pool by default — see ``api/jobs.py``. Every send
costs a round trip to Brevo, and a registration that also has to tell the whole
office about a declaration makes several of them; paying for those inline put
the wait in front of the person registering, who gains nothing by it. Where the
*answer* is shown to somebody, ``background=False`` keeps the send inline, and
the two places that do that are the mail panel's test message and the account
decision that warns the office when the applicant could not be reached.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

from . import jobs

logger = logging.getLogger(__name__)

_TONE = {
    'Approved': ('success', 'has been approved'),
    'Rejected': ('warning', 'was not approved'),
    'Needs Revision': ('warning', 'needs changes before it can be approved'),
    'Pending Validation': ('info', 'is being reviewed'),
    'Pending': ('info', 'is being reviewed'),
}


def _recipient(target):
    """Resolve any notification target to ``(profile, address)``.

    Callers hold a profile, a user or a bare address depending on where
    they sit, and a person may have an address but no profile — an
    imported scholar, say — so both halves are returned and either may be
    empty.
    """
    from .models import StudentProfile, User

    if isinstance(target, StudentProfile):
        return target, (target.user.email or '')
    if isinstance(target, User):
        return StudentProfile.objects.filter(user=target).first(), (target.email or '')
    if isinstance(target, str):
        return None, target.strip()
    return None, ''


def _record_attempt(to, subject, error):
    """Remember the outcome of the last send, for the office's mail panel.

    The deployment has no shell, so this row is how anyone finds out
    whether mail is working. Wrapped in its own try: failing to record a
    failure must not raise on top of it.
    """
    from django.utils import timezone

    try:
        from .models import SystemSettings
        SystemSettings.objects.update_or_create(
            pk=1,
            defaults={
                'last_mail_attempt_at': timezone.now(),
                'last_mail_to': (to or '')[:254],
                'last_mail_subject': (subject or '')[:200],
                'last_mail_error': error,
            },
        )
    except Exception:
        logger.exception('Could not record the outcome of the last mail attempt')


def queue_email(to, subject, body):
    """Hand one message to the background pool.

    The caller gets no outcome because there is not one yet. What there is
    instead is the row :func:`_record_attempt` writes when the send finishes,
    which the office's mail panel reads — and which outlives the request,
    where a return value would only have been true for the length of one.
    """
    if not to:
        return
    jobs.enqueue(send_email, to, subject, body,
                 label=f'email to {to}: {subject[:60]}')


def send_email(to, subject, body):
    """Send one message now, reporting success rather than raising.

    Deliberately swallows the error. Every caller is doing something more
    important than the email — recording a decision, creating an account —
    and none of them should be rolled back because a mail server was
    briefly unreachable. The outcome is recorded for the office instead.
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
    except Exception as exc:
        logger.exception('Could not email %s: %s', to, subject)
        _record_attempt(to, subject, str(exc) or exc.__class__.__name__)
        return False
    _record_attempt(to, subject, '')
    return True


def notify(target, title, body, tone='info', email=True, email_body=None,
           background=True):
    """Tell someone something, in the portal and by email.

    The in-app notification is the reliable half and is written first; the
    email is best-effort.

    Returns ``(in_app, emailed)``. ``emailed`` is ``None`` when the message
    was queued rather than sent, because at that point nobody knows — pass
    ``background=False`` wherever that answer is about to be shown to
    somebody, and read it as "unknown" rather than "no" anywhere else.
    """
    from .models import Notification

    profile, address = _recipient(target)

    in_app = False
    if profile is not None:
        Notification.objects.create(
            student=profile, type=tone, title=title, body=body,
        )
        in_app = True

    if not email:
        return in_app, False
    subject, text = f'[BiPSU SRMS] {title}', email_body or body
    if background:
        queue_email(address, subject, text)
        return in_app, None
    return in_app, send_email(address, subject, text)


def account_decision(account, status, note):
    """Tell an applicant the office's verdict on their registration."""
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
        background=False,
    )


def broadcast(title, body, tone='info'):
    """Send one announcement to many students at once."""
    from .models import Notification, StudentProfile

    profiles = list(StudentProfile.objects.only('id'))
    Notification.objects.bulk_create([
        Notification(student=p, type=tone, title=title, body=body)
        for p in profiles
    ])
    return len(profiles)


def _send_each(addresses, subject, body):
    """Send one message to every address, counting the ones that landed."""
    return sum(send_email(to, subject, body) for to in addresses)


def office(subject, body, actor=None, background=True):
    """Tell the SDSO something, and log it.

    Goes to every active office account rather than a fixed address, so it
    keeps working when staff change. That fan-out is why this queues by
    default: it is one round trip per office account, and the caller is
    normally a student registering, who is made to wait out every one.

    Returns how many addresses the message was aimed at when queued, and how
    many it reached when sent inline.
    """
    from .models import ActivityLog, User

    ActivityLog.record(actor, f'{subject} — {body}', verb='other')

    addresses = list(User.objects.filter(
        role='vpsea', is_active=True,
    ).exclude(email='').values_list('email', flat=True))
    line = f'[BiPSU SRMS] {subject}'
    if background:
        jobs.enqueue(_send_each, addresses, line, body,
                     label=f'office mail: {subject[:60]}')
        return len(addresses)
    return _send_each(addresses, line, body)


def multiple_declarations(profile, declarations):
    """Warn the office that one registrant declared several awards."""
    from .constants import scholarship_type_labels

    labels = scholarship_type_labels()
    named = ', '.join(labels.get(d['scholarship_type'], d['scholarship_type'])
                      for d in declarations)
    student = profile.user.get_full_name() or profile.user.email

    lines = [
        f'{student} ({profile.student_id}) registered declaring '
        f'{len(declarations)} scholarships: {named}.',
        'Each one is waiting as its own link request on the account '
        'verification queue, with its own proof document, and each is verified '
        'or refused separately — approving the account decides all of them at '
        'once, so read every card before you do.',
    ]
    if getattr(settings, 'SITE_URL', ''):
        lines.append(f'The queue is here: {settings.SITE_URL}/vpsea/accounts/')

    return office(f'{student} declared {len(declarations)} scholarships',
                  '\n\n'.join(lines))


def scholarship_added(profile, declarations):
    """Tell a student the office recorded a scholarship for them."""
    from .constants import scholarship_type_labels

    labels = scholarship_type_labels()
    named = ', '.join(labels.get(d['scholarship_type'], d['scholarship_type'])
                      for d in declarations)
    student = profile.user.get_full_name() or profile.user.email
    plural = 'scholarships' if len(declarations) > 1 else 'a scholarship'

    lines = [
        f'{student} ({profile.student_id}) has added {plural} to their '
        f'account: {named}.',
        'They registered before they held it, so it was not part of the '
        'account you already verified. Each one waits under "Scholarships '
        'added by verified students" on Account Verification, with its own '
        'proof document, and each is verified or refused on its own.',
    ]
    if getattr(settings, 'SITE_URL', ''):
        lines.append(f'They are waiting here: {settings.SITE_URL}/vpsea/accounts/')

    return office(f'{student} added {plural}: {named}', '\n\n'.join(lines))


def decision(target, subject, status, remarks='', detail='', link=''):
    """Tell an applicant their application was approved or refused."""
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
