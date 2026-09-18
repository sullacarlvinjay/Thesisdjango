import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

_TONE = {
    'Approved': ('success', 'has been approved'),
    'Rejected': ('warning', 'was not approved'),
    'Needs Revision': ('warning', 'needs changes before it can be approved'),
    'Pending Validation': ('info', 'is being reviewed'),
    'Pending': ('info', 'is being reviewed'),
}


def _recipient(target):
    from .models import StudentProfile, User

    if isinstance(target, StudentProfile):
        return target, (target.user.email or '')
    if isinstance(target, User):
        return StudentProfile.objects.filter(user=target).first(), (target.email or '')
    if isinstance(target, str):
        return None, target.strip()
    return None, ''


def _record_attempt(to, subject, error):
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


def send_email(to, subject, body):
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


def notify(target, title, body, tone='info', email=True, email_body=None):
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
    from .models import Notification, StudentProfile

    profiles = list(StudentProfile.objects.only('id'))
    Notification.objects.bulk_create([
        Notification(student=p, type=tone, title=title, body=body)
        for p in profiles
    ])
    return len(profiles)


def office(subject, body, actor=None):
    from .models import ActivityLog, User

    ActivityLog.objects.create(user=actor, action=f'{subject} — {body}')

    addresses = list(User.objects.filter(
        role='vpsea', is_active=True,
    ).exclude(email='').values_list('email', flat=True))
    return sum(send_email(to, f'[BiPSU SRMS] {subject}', body) for to in addresses)


def multiple_declarations(profile, declarations):
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
