"""Values every template needs, kept off the per-request query budget.

This module runs on every single page render, so anything it reads is read
tens of thousands of times a day for data that changes a few times a term.
The active term in particular was a database round trip on every request,
including requests that never looked at it.

Each cached value is keyed by what it depends on and given a lifetime matched
to how much staleness it can carry:

``term``
    Changes when the office rolls the semester, which is a handful of times a
    year. Held for five minutes and cleared outright when ``SystemSettings``
    is saved, so a rollover is visible immediately rather than after a wait.
``pending``
    A badge counter. Thirty seconds late is invisible to a reader and saves
    two queries on every office page.
``standing``
    Gates a nav link for one student. Sixty seconds, and the view behind the
    link re-checks before acting, so a stale value cannot let anyone through.

The cache is also the throttle's store; see ``api/ratelimit.py`` for what
happens when no Redis is configured.
"""

from django.core.cache import cache

TERM_KEY = 'ctx:active-term'
TERM_SECONDS = 300
PENDING_SECONDS = 30
STANDING_SECONDS = 60


def system_settings(request):
    """Everything the base template needs, on every request.

    Each value is cached; see the module docstring for the lifetimes and
    why each one can carry the staleness it does.
    """
    ctx = dict(_active_term())
    ctx['pending_accounts'] = _pending_accounts(request)
    ctx['profile_photo_url'] = _profile_photo_url(request)
    ctx['support_email'] = _support_email()
    ctx['canonical_url'] = _canonical_url(request)
    ctx.update(_scholarship_standing(request))
    ctx.update(_window_state(request))
    return ctx


def _active_term():
    """The active semester and school year, read once per five minutes."""
    cached = cache.get(TERM_KEY)
    if cached is not None:
        return cached

    from .models import SystemSettings
    try:
        settings_obj = SystemSettings.objects.get(pk=1)
        parsed = SystemSettings.parse_label(settings_obj.academic_year)
        value = {'active_semester': parsed['semester'],
                 'academic_year': parsed['sy']}
    except Exception:
        return {'active_semester': '', 'academic_year': ''}

    cache.set(TERM_KEY, value, TERM_SECONDS)
    return value


def forget_active_term(**_kwargs):
    """Drop the cached term. Connected to ``SystemSettings`` saves."""
    cache.delete(TERM_KEY)


def _canonical_url(request):
    """The canonical URL for this page, or '' if it cannot be built."""
    from .seo import canonical_url
    try:
        return canonical_url(request)
    except Exception:
        return ''


def _support_email():
    """The address shown on error and help pages."""
    from django.conf import settings
    return getattr(settings, 'SUPPORT_EMAIL', '')


AVATAR_SECONDS = 600


def _profile_photo_url(request):
    """The signed-in user's avatar URL, resolved once every ten minutes.

    ``photo_url`` reads the file field, and on the deployed configuration that
    means asking the object store to build a URL — on every render of every
    page, for a value that changes when someone uploads a new picture and
    never otherwise. Keyed by the stored filename, so a new upload is a new
    key and takes effect at once rather than waiting for the old one to
    expire.
    """
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated):
        return ''

    stored = getattr(user.photo, 'name', '') or ''
    if not stored:
        return ''

    key = f'ctx:avatar:{user.pk}:{stored}'
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        url = user.photo_url
    except Exception:
        return ''
    cache.set(key, url, AVATAR_SECONDS)
    return url



WINDOW_SECONDS = 60


def _window_state(request):
    """Whether applications and renewals are open for this person right now.

    The nav reads this to hide a tab rather than offer a page that will only
    refuse, and the dashboard reads it to say why. Both need the same answer,
    so it is worked out once here instead of in each template.

    Returns:
        ``applications_open``, ``renewals_open`` and, when either is shut,
        ``applications_closed_reason`` / ``renewals_closed_reason`` — the
        office's own wording, which says when the window reopens rather than
        only that it is shut.
    """
    shut = {'applications_open': False, 'renewals_open': False,
            'applications_closed_reason': '', 'renewals_closed_reason': ''}
    user = getattr(request, 'user', None)
    role = getattr(user, 'role', '') if user and user.is_authenticated else ''
    if role not in ('student', 'nsu_staff'):
        return shut

    key = f'ctx:windows:{role}:{user.pk}'
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        state = _windows_for(user, role)
    except Exception:
        return shut

    cache.set(key, state, WINDOW_SECONDS)
    return state


def _windows_for(user, role):
    """Work out the window state for one account."""
    from .views_shared import (application_window_reason,
                               held_scholarship_types,
                               renewal_window_reason)

    if role == 'nsu_staff':
        applications = application_window_reason('Staff')
        renewals = renewal_window_reason('Staff')
    else:
        from .models import StudentProfile
        profile = StudentProfile.objects.filter(user=user).first()
        applications = application_window_reason('Academic')

        held = sorted(held_scholarship_types(profile))
        reasons = [renewal_window_reason(stype) for stype in held]
        if not held:
            renewals = 'You have no scholarship to renew yet.'
        elif any(not reason for reason in reasons):
            renewals = ''
        else:
            renewals = ' '.join(reason for reason in reasons if reason)

    return {
        'applications_open': not applications,
        'renewals_open': not renewals,
        'applications_closed_reason': applications,
        'renewals_closed_reason': renewals,
    }


def _scholarship_standing(request):
    """Whether this student holds an award, and may apply for an academic one."""
    closed = {'enrolled': False, 'can_apply_academic': False}
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and getattr(user, 'role', '') == 'student'):
        return closed

    key = f'ctx:standing:{user.pk}'
    cached = cache.get(key)
    if cached is not None:
        return cached

    from .models import StudentProfile
    from .views_shared import can_hold_alongside, held_scholarship_types
    try:
        held = held_scholarship_types(
            StudentProfile.objects.filter(user=user).first())
    except Exception:
        return closed

    value = {
        'enrolled': bool(held),
        'can_apply_academic': can_hold_alongside(held, 'Academic'),
    }
    cache.set(key, value, STANDING_SECONDS)
    return value


def forget_scholarship_standing(user_id):
    """Drop one student's cached standing after their awards change."""
    cache.delete(f'ctx:standing:{user_id}')


def _pending_accounts(request):
    """How many registrations are waiting, for the office's sidebar badge."""
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and getattr(user, 'role', '') == 'vpsea'):
        return 0

    cached = cache.get('ctx:pending-accounts')
    if cached is not None:
        return cached

    from .models import User
    from .views_declarations import pending_declarations
    try:
        total = User.objects.filter(
            verification_status='pending', role__in=('student', 'nsu_staff'),
        ).count() + pending_declarations().count()
    except Exception:
        return 0

    cache.set('ctx:pending-accounts', total, PENDING_SECONDS)
    return total
