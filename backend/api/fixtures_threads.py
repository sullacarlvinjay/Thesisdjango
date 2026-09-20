"""Making SQLite behave enough to test threaded work against.

The suite runs on one in-memory SQLite database opened in shared-cache mode,
which is how a pool thread gets to see what the request wrote. Shared cache
also locks per table, and it does not make a blocked caller wait: it refuses it
outright with "database table is locked". Both halves of that bite here.

A reader holding a table lock refuses a writer, which ``PRAGMA read_uncommitted``
settles by not taking the lock at all. A second *writer* is refused as well, and
no pragma helps with that -- so the pool is held shut until the request that
queued the job has handed its connection back. The deployment runs Postgres,
where two writers touching different rows are not a race at all, and file-backed
SQLite raises the retryable SQLITE_BUSY rather than this. The lock is an artefact
of the test database, so it is answered in the test fixture rather than worked
around in ``api/jobs.py``.
"""

import threading

from django.conf import settings
from django.db import connection, connections
from django.db.backends.signals import connection_created

from api import jobs

RECEIVER = 'srms.tests.read_uncommitted'


def _read_uncommitted(sender, connection, **kwargs):
    """Let this connection read without locking the table against writers."""
    if connection.vendor != 'sqlite':
        return
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA read_uncommitted = 1;')


class ThreadedSqliteMixin:
    """Mix into a case that drives the background pool against the database.

    Every worker is occupied by a job that waits on a gate, so nothing the case
    queues can start until :meth:`settle` opens it. That makes the ordering the
    case asserts on the ordering it actually gets, rather than whichever one the
    scheduler happened to pick.
    """

    @classmethod
    def setUpClass(cls):
        connection_created.connect(_read_uncommitted, dispatch_uid=RECEIVER)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        connection_created.disconnect(dispatch_uid=RECEIVER)
        jobs.shutdown()

    def setUp(self):
        super().setUp()
        for alias in connections:
            _read_uncommitted(None, connections[alias])
        self.gate = threading.Event()
        self.addCleanup(self.gate.set)
        self._hold_the_pool()

    def _hold_the_pool(self):
        """Fill every worker with a job that waits for the gate."""
        jobs.shutdown()
        workers = max(1, int(getattr(settings, 'BACKGROUND_WORKERS', 2)))
        for n in range(workers):
            jobs.enqueue(self.gate.wait, 30, label=f'gate-{n}')

    def settle(self, timeout=20):
        """Hand back this thread's connection, open the gate, wait for the pool.

        Gunicorn releases the connection when the response goes out; a case that
        holds on to it is the one thing standing between the pool thread and the
        row it is trying to write.
        """
        connection.close()
        self.gate.set()
        return jobs.drain(timeout=timeout)
