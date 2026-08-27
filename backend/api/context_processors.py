def system_settings(request):
    from .models import SystemSettings
    try:
        s = SystemSettings.objects.get(pk=1)
        parsed = SystemSettings.parse_label(s.academic_year)
        ctx = {'active_semester': parsed['semester'], 'academic_year': parsed['sy']}
    except Exception:
        ctx = {'active_semester': '', 'academic_year': ''}
    ctx['pending_link_requests'] = _pending_link_requests(request)
    ctx['pending_accounts'] = _pending_accounts(request)
    return ctx


def _pending_link_requests(request):
    """Badge count for the VPSEA sidebar. Only queried for VPSEA users so the
    student and UniFAST pages do not pay for it."""
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and getattr(user, 'role', '') == 'vpsea'):
        return 0
    from .models import ScholarshipLinkRequest
    try:
        return ScholarshipLinkRequest.objects.filter(status='Pending').count()
    except Exception:
        return 0


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
