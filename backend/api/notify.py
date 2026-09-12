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


def _record_attempt(to, subject, error):
    """Keep what became of the last send, for the office's mail panel.

    Best-effort inside a function that is already best-effort: this runs on the
    failure path of something that must not raise, so a database that is down
    while mail is also down must not turn a logged warning into a 500. The log
    line above is the durable record; this is the copy somebody can actually
    read without a shell.
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
    except Exception:                                   # noqa: BLE001
        logger.exception('Could not record the outcome of the last mail attempt')


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
    except Exception as exc:                            # noqa: BLE001
        # Bad credentials, no network, a refused relay — all the same to us.
        logger.exception('Could not email %s: %s', to, subject)
        # str(exc) rather than the class: the useful half of a BrevoSendError
        # is the provider's own wording, and of an SMTP error the server's.
        _record_attempt(to, subject, str(exc) or exc.__class__.__name__)
        return False
    _record_attempt(to, subject, '')
    return True


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


def office(subject, body, actor=None):
    """Tell the SDSO something its queue counts cannot say on their own.

    Every other function here writes to an applicant. This one goes the other
    way, and it exists because the office's only standing signal is a badge
    counting *accounts* waiting to be verified — which says nothing about what
    any of them contains. A registration that needs a closer look is
    indistinguishable from one that does not until somebody opens it.

    Two channels, for the two ways an officer finds out:

    * **Email**, to every active VPSEA account. There is no in-app bell for
      staff — ``Notification`` hangs off ``StudentProfile`` — so this is the
      only thing that reaches an officer who is not already on the page.
    * **ActivityLog**, which survives whatever mail does. Delivery here is
      best-effort like every send in this module, and a warning nobody can find
      afterwards is a warning that was never given.

    Returns how many addresses it reached.
    """
    from .models import ActivityLog, User

    ActivityLog.objects.create(user=actor, action=f'{subject} — {body}')

    addresses = list(User.objects.filter(
        role='vpsea', is_active=True,
    ).exclude(email='').values_list('email', flat=True))
    return sum(send_email(to, f'[BiPSU SRMS] {subject}', body) for to in addresses)


def multiple_declarations(profile, declarations):
    """Tell the SDSO that one registration declared more than one scholarship.

    The ordinary registration declares nothing, and the next most ordinary
    declares one. Two or more is the case the office asked to be told about:
    each one is a separate link request to check against a separate set of
    records, and the account queue shows them stacked inside a single card that
    an officer skimming a list has no reason to open.

    Named for the situation rather than for the channel, so the wording of this
    warning lives in one place and cannot drift between the registration path
    and anything that later wants to raise the same flag.
    """
    from .constants import DECLARABLE_SCHOLARSHIP_TYPES

    labels = dict(DECLARABLE_SCHOLARSHIP_TYPES)
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
