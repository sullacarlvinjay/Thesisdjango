from django.conf import settings
from django.http import HttpResponse


DISALLOWED_PREFIXES = (
    '/student/',
    '/nsu-staff/',
    '/vpsea/',
    '/partner/',
    '/api/',
    '/admin/',
    '/media/',
)


def site_origin(request):
    base = (getattr(settings, 'SITE_URL', '') or '').strip().rstrip('/')
    if base:
        return base
    try:
        return request.build_absolute_uri('/').rstrip('/')
    except Exception:
        return ''


def canonical_url(request):
    path = getattr(request, 'path', '') or '/'
    origin = site_origin(request)
    if not origin:
        return ''
    return origin + path


def robots_txt(request):
    lines = ['User-agent: *']
    lines.extend('Disallow: ' + prefix for prefix in DISALLOWED_PREFIXES)
    body = '\n'.join(lines) + '\n'
    response = HttpResponse(body, content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=86400'
    return response
