"""Liveness and readiness endpoints.

``/healthz/`` exists to be polled. The deployment runs on a plan that suspends
the container after about fifteen minutes without traffic, and the next visitor
then waits roughly fifty seconds for it to start again. An external monitor
hitting this endpoint every ten minutes keeps the container awake, so the
person who actually needs the site is not the one paying for the restart.

It therefore has to be cheap: no database, no cache, no template. A health
check that queried Postgres would add load on every poll and would report the
process dead whenever the database merely hiccuped.

``/readyz/`` is the opposite, and is for deploys rather than for polling: it
does touch the database and the configured storage, and reports which
dependency is unreachable.
"""

import time

from django.http import JsonResponse

STARTED_AT = time.monotonic()


def healthz(request):
    """Report that the process is up, without touching any dependency."""
    response = JsonResponse({
        'status': 'ok',
        'uptime_seconds': round(time.monotonic() - STARTED_AT, 1),
    })
    response['Cache-Control'] = 'no-store'
    return response


def readyz(request):
    """Report whether the dependencies this deploy needs are actually reachable.

    Used after a deploy and when something looks wrong. Returns 503 with the
    failing component named, rather than a bare failure, so the cause does not
    have to be guessed from logs.
    """
    checks = {}

    start = time.monotonic()
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        checks['database'] = {'ok': True,
                              'ms': round((time.monotonic() - start) * 1000, 1)}
    except Exception as failure:
        checks['database'] = {'ok': False, 'error': type(failure).__name__}

    start = time.monotonic()
    try:
        from django.core.cache import cache
        cache.set('healthz:probe', 1, 10)
        checks['cache'] = {'ok': True,
                           'ms': round((time.monotonic() - start) * 1000, 1)}
    except Exception as failure:
        checks['cache'] = {'ok': False, 'error': type(failure).__name__}

    healthy = all(entry['ok'] for entry in checks.values())
    response = JsonResponse(
        {'status': 'ok' if healthy else 'degraded', 'checks': checks},
        status=200 if healthy else 503)
    response['Cache-Control'] = 'no-store'
    return response
