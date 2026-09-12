def system_settings(request):
    from .models import SystemSettings
    try:
        s = SystemSettings.objects.get(pk=1)
        parsed = SystemSettings.parse_label(s.academic_year)
        ctx = {'active_semester': parsed['semester'], 'academic_year': parsed['sy']}
    except Exception:
        ctx = {'active_semester': '', 'academic_year': ''}
    ctx['pending_accounts'] = _pending_accounts(request)
    ctx['profile_photo_url'] = _profile_photo_url(request)
    ctx.update(_scholarship_standing(request))
    return ctx


def _profile_photo_url(request):
    """URL of the signed-in user's profile photo, or '' when none is set."""
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return user.photo_url
    return ''


def _scholarship_standing(request):
    """What this student holds, and which programmes are therefore still open.

    The student nav hides an Apply page once that programme is closed to them.
    Individual views used to compute this for their own template, which meant
    the nav quietly showed the wrong thing on every page that forgot to.
    Answered here instead, so it is right on all of them.
    """
    closed = {'enrolled': False, 'can_apply_academic': False}
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and getattr(user, 'role', '') == 'student'):
        return closed
    from .models import StudentProfile
    from .student_views import can_hold_alongside, held_scholarship_types
    try:
        held = held_scholarship_types(
            StudentProfile.objects.filter(user=user).first())
    except Exception:
        return closed
    return {
        'enrolled': bool(held),
        'can_apply_academic': can_hold_alongside(held, 'Academic'),
    }


def _pending_accounts(request):
    """Badge count for the account verification queue, VPSEA users only.

    Registrations pile up unseen otherwise — nobody can sign in until someone
    looks at them.
    """
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and getattr(user, 'role', '') == 'vpsea'):
        return 0
    from .models import User
    try:
        return User.objects.filter(
            verification_status='pending', role__in=('student', 'nsu_staff'),
        ).count()
    except Exception:
        return 0
