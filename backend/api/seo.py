"""Canonical URLs and robots.txt.

Everything behind a sign-in is disallowed to crawlers. Not as a security
measure, since the portals are already gated, but so that sign-in walls are not
indexed and scholar documents never appear in search results.
"""

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
    """The site's public origin, for building absolute links.

    ``SITE_URL`` wins when it is set, because a link in an email has to
    work from outside and the request's own host may be an internal one.
    """
    base = (getattr(settings, 'SITE_URL', '') or '').strip().rstrip('/')
    if base:
        return base
    try:
        return request.build_absolute_uri('/').rstrip('/')
    except Exception:
        return ''


def canonical_url(request):
    """The canonical absolute URL for this request, or ''."""
    path = getattr(request, 'path', '') or '/'
    origin = site_origin(request)
    if not origin:
        return ''
    return origin + path


def robots_txt(request):
    """Serve ``/robots.txt``.

    Everything behind a sign-in is disallowed. Not as a security measure —
    the portals are already gated — but so that search engines do not
    index sign-in walls, and so scholar documents never appear in results.
    """
    lines = ['User-agent: *']
    lines.extend('Disallow: ' + prefix for prefix in DISALLOWED_PREFIXES)
    body = '\n'.join(lines) + '\n'
    response = HttpResponse(body, content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=86400'
    return response
