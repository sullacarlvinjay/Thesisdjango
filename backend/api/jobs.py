"""Work that outlives the request that asked for it.

A request that sends mail, renders a masterlist or reads a spreadsheet does
none of those things for the person waiting on it. Until this module existed
they all ran inline, so a registration that also had to tell four office
accounts about a declaration paid four mail round trips -- ``EMAIL_TIMEOUT``
seconds each, at worst -- before the browser saw anything at all.

Deliberately in-process. Celery and RQ both want a broker and a second service,
and this deploys to a free Render instance with neither: one container running
``--workers 1 --threads 8`` against a database it does not own. A thread pool
inside that container needs nothing new and hands the request thread back
immediately, which is the whole of the problem.

What it cannot do is survive a restart. A queued job is gone when Render
redeploys or the instance idles out, so work whose loss would otherwise be
silent carries a ``BackgroundJob`` row: the row is written before the job is
queued, and a row still marked ``running`` long after a restart is one nobody
is going to finish. Nothing here retries by itself. The office does, from a row
it can see.

Under ``BACKGROUND_JOBS_SYNCHRONOUS`` -- on by default while the tests run --
every job runs inline on the calling thread, so a case asserts against a
finished state rather than against a race.
"""

import atexit
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)

_pool = None
_pending = 0
_idle = threading.Condition()


def synchronous():
    """Whether jobs run on the calling thread instead of being queued."""
    return bool(getattr(settings, 'BACKGROUND_JOBS_SYNCHRONOUS', False))


def _sized(name, fallback):
    """A positive integer setting, falling back when it is missing or junk."""
    try:
        return max(1, int(getattr(settings, name, fallback)))
    except (TypeError, ValueError):
        return fallback


def _pool_for_submission():
    """The shared pool, built on first use.

    Lazily rather than at import, so a management command that queues nothing
    -- ``migrate``, ``collectstatic`` -- does not start threads it would only
    have to shut down again.
    """
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(
            max_workers=_sized('BACKGROUND_WORKERS', 2),
            thread_name_prefix='srms-job')
        atexit.register(shutdown)
    return _pool


def _named(label, fn):
    """What to call this job in the log."""
    return label or getattr(fn, '__name__', repr(fn))


def _execute(label, fn, args, kwargs, threaded=False):
    """Run one job without letting it take the worker thread down with it.

    A worker that died on an exception would take the pool's capacity with it
    one job at a time, and silently, which is the failure mode worth spending a
    try block on.

    Connections are closed on the way out only when this ran on a pool thread.
    ``CONN_MAX_AGE`` is 600 in production, so a worker thread that did not
    close would sit on a Supabase pooler connection for ten minutes after
    finishing with it. Closing on the *request* thread would instead take away
    the connection the request is still using, which is why the inline path
    leaves it alone.
    """
    global _pending
    try:
        fn(*args, **kwargs)
    except Exception:
        logger.exception('Background job %r failed', _named(label, fn))
    finally:
        if threaded:
            connections.close_all()
            with _idle:
                _pending -= 1
                _idle.notify_all()


def enqueue(fn, *args, label='', **kwargs):
    """Run ``fn`` away from the request thread.

    Returns nothing. A caller that waits for the answer has not moved the work
    anywhere, so anything it needs to know afterwards belongs in a
    ``BackgroundJob`` row rather than in a return value.

    A full queue runs the job inline rather than dropping it. A backlog long
    enough to reach the limit is one where the alternatives are losing work or
    growing the queue until the container is killed for memory, and on 512 MB
    that is not a backlog worth keeping.
    """
    global _pending
    if synchronous():
        _execute(label, fn, args, kwargs)
        return

    with _idle:
        room = _pending < _sized('BACKGROUND_QUEUE_LIMIT', 50)
        if room:
            _pending += 1
            pool = _pool_for_submission()

    if not room:
        logger.warning('Background queue is full; running %r on the request '
                       'thread', _named(label, fn))
        _execute(label, fn, args, kwargs)
        return

    try:
        pool.submit(_execute, label, fn, args, kwargs, threaded=True)
    except RuntimeError:
        with _idle:
            _pending -= 1
            _idle.notify_all()
        logger.warning('Background pool is closed; running %r on the request '
                       'thread', _named(label, fn))
        _execute(label, fn, args, kwargs)


def pending():
    """How many jobs are queued or running."""
    with _idle:
        return _pending


def drain(timeout=30):
    """Wait for the queue to empty, reporting whether it did.

    For tests and for an orderly shutdown. A view that calls this has undone
    the point of the module.
    """
    deadline = time.monotonic() + timeout
    with _idle:
        while _pending:
            left = deadline - time.monotonic()
            if left <= 0:
                return False
            _idle.wait(left)
    return True


def shutdown(wait=True):
    """Stop the pool, letting what is already running finish.

    Registered with ``atexit`` the first time a pool is built, so a queued job
    is not simply abandoned when the process is asked to stop.
    """
    global _pool
    with _idle:
        current, _pool = _pool, None
    if current is not None:
        current.shutdown(wait=wait)
