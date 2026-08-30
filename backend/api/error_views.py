"""The pages people see when something goes wrong.

Django's own are plain text written for the developer — "Forbidden (403). CSRF
verification failed. Request aborted. More information is available with
DEBUG=True." An applicant reading that on their phone has been told they did
something forbidden, given a hint that only helps someone with the source code,
and offered no way forward. Every one of these replaces that with the plain
reason and a link out.

The CSRF page is the one that actually gets hit. It is almost never an attack:
it is a form left open past the session's life, a browser refusing cookies, or
the back button after a sign-out.
"""

from django.conf import settings
from django.shortcuts import render
from django.template import loader
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
)


CSRF_TEMPLATE = 'errors/403_csrf.html'


def _retry_url(request):
    """Where 'try again' should point.

    The page they were posting to is the sensible place for someone still
    signed in. Anyone else is sent to sign in, with the page they wanted kept
    on the query string so they land back on it.
    """
    path = request.path or '/'
    if request.user.is_authenticated:
        # A POST-only endpoint would just fail again on GET, so send them to
        # the page the form lived on where the referer names it.
        referer = request.META.get('HTTP_REFERER', '')
        if referer:
            return referer
        return path
    return '/login/'


def csrf_failure(request, reason='', template_name=CSRF_TEMPLATE):
    """Wired up by settings.CSRF_FAILURE_VIEW."""
    ctx = {
        'reason': reason,
        'retry_url': _retry_url(request),
        # The raw reason is a developer's sentence. Show it only where a
        # developer is the one reading.
        'debug': settings.DEBUG,
    }
    return HttpResponseForbidden(
        loader.render_to_string(template_name, ctx, request=request),
        content_type='text/html',
    )


def bad_request(request, exception=None, template_name='errors/400.html'):
    return HttpResponseBadRequest(
        loader.render_to_string(template_name, {}, request=request))


def permission_denied(request, exception=None, template_name='errors/403.html'):
    return HttpResponseForbidden(
        loader.render_to_string(template_name, {}, request=request))


def page_not_found(request, exception=None, template_name='errors/404.html'):
    return HttpResponseNotFound(
        loader.render_to_string(template_name, {}, request=request))


def server_error(request, template_name='errors/500.html'):
    """No request context on purpose.

    Whatever raised the 500 may well have been a context processor or the
    session store, so this page is rendered with nothing at all behind it.
    """
    return HttpResponseServerError(
        loader.render_to_string(template_name, {}))
