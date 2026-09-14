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
    path = request.path or '/'
    if request.user.is_authenticated:
        referer = request.META.get('HTTP_REFERER', '')
        if referer:
            return referer
        return path
    return '/login/'


def csrf_failure(request, reason='', template_name=CSRF_TEMPLATE):
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
    return HttpResponseBadRequest(
        loader.render_to_string(template_name, {}, request=request))


def permission_denied(request, exception=None, template_name='errors/403.html'):
    return HttpResponseForbidden(
        loader.render_to_string(template_name, {}, request=request))


def page_not_found(request, exception=None, template_name='errors/404.html'):
    return HttpResponseNotFound(
        loader.render_to_string(template_name, {}, request=request))


def server_error(request, template_name='errors/500.html'):
    return HttpResponseServerError(
        loader.render_to_string(template_name, {}))
