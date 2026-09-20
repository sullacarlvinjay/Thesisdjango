"""Error pages.

Custom handlers for 400, 403, 404, 500 and CSRF failure. The CSRF page matters
most: its usual cause is innocent — a form left open until the token expired —
and Django's default tells the reader nothing they can act on.
"""

from django.conf import settings
from django.template import loader
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
)


CSRF_TEMPLATE = 'errors/403_csrf.html'


def _retry_url(request):
    """Where the "try again" link on an error page should go.

    Back where they were if they are signed in and the browser said where
    that was; otherwise the sign-in page, since an anonymous visitor
    hitting an error usually needs to sign in.
    """
    path = request.path or '/'
    if request.user.is_authenticated:
        referer = request.META.get('HTTP_REFERER', '')
        if referer:
            return referer
        return path
    return '/login/'


def csrf_failure(request, reason='', template_name=CSRF_TEMPLATE):
    """Render the CSRF failure page.

    A dedicated page rather than Django's default, because the usual cause
    is an innocent one — a form left open until the token expired — and
    the default tells the reader nothing they can act on. This one offers
    the way back.
    """
    ctx = {
        'reason': reason,
        'retry_url': _retry_url(request),
        'debug': settings.DEBUG,
    }
    return HttpResponseForbidden(
        loader.render_to_string(template_name, ctx, request=request),
        content_type='text/html',
    )


def bad_request(request, exception=None, template_name='errors/400.html'):
    """Render the 400 page."""
    return HttpResponseBadRequest(
        loader.render_to_string(template_name, {}, request=request))


def permission_denied(request, exception=None, template_name='errors/403.html'):
    """Render the 403 page."""
    return HttpResponseForbidden(
        loader.render_to_string(template_name, {}, request=request))


def page_not_found(request, exception=None, template_name='errors/404.html'):
    """Render the 404 page."""
    return HttpResponseNotFound(
        loader.render_to_string(template_name, {}, request=request))


def server_error(request, template_name='errors/500.html'):
    """Render the 500 page.

    Takes no request context: whatever broke may be in a context
    processor, and a 500 handler that raises is a blank page.
    """
    return HttpResponseServerError(
        loader.render_to_string(template_name, {}))
