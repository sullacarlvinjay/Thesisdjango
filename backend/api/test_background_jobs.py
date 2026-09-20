"""What the background pool promises, and what it deliberately does not.

Every other module in the suite runs with ``BACKGROUND_JOBS_SYNCHRONOUS`` on,
which is what keeps those cases asserting against a finished state instead of a
race. That makes this the only place the threaded path is exercised at all, so
the cases here turn it back on and wait on :func:`api.jobs.drain`.
"""

import threading

from django.core import mail
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from api import jobs, notify
from api.fixtures_threads import ThreadedSqliteMixin
from api.models import Notification, StudentProfile, User

THREADED = {'BACKGROUND_JOBS_SYNCHRONOUS': False}


class InlineJobTest(SimpleTestCase):
    """With the pool switched off, a job is just a function call."""

    @override_settings(BACKGROUND_JOBS_SYNCHRONOUS=True)
    def test_the_work_is_finished_by_the_time_enqueue_returns(self):
        done = []
        jobs.enqueue(done.append, 'ran')
        self.assertEqual(done, ['ran'],
                         'a synchronous job had not run when enqueue returned')

    @override_settings(BACKGROUND_JOBS_SYNCHRONOUS=True)
    def test_it_runs_on_the_calling_thread(self):
        where = []
        jobs.enqueue(lambda: where.append(threading.current_thread().name))
        self.assertEqual(where, [threading.current_thread().name])


@override_settings(**THREADED)
class ThreadedJobTest(SimpleTestCase):
    """With the pool on, the caller is released and the work still happens."""

    def tearDown(self):
        jobs.drain(timeout=10)

    def test_the_job_runs_somewhere_that_is_not_the_caller(self):
        where = []
        started = threading.Event()

        def record():
            where.append(threading.current_thread().name)
            started.set()

        jobs.enqueue(record, label='where')
        self.assertTrue(started.wait(10), 'the job never ran')
        self.assertNotEqual(
            where, [threading.current_thread().name],
            'the work stayed on the thread it was supposed to leave')

    def test_drain_waits_for_the_queue_to_empty(self):
        done = []
        for n in range(6):
            jobs.enqueue(done.append, n, label=f'job-{n}')
        self.assertTrue(jobs.drain(timeout=15), 'the queue never emptied')
        self.assertCountEqual(done, range(6))
        self.assertEqual(jobs.pending(), 0)

    def test_a_job_that_raises_does_not_take_the_worker_with_it(self):
        def explode():
            raise RuntimeError('deliberate')

        with self.assertLogs('api.jobs', level='ERROR') as logged:
            jobs.enqueue(explode, label='explode')
            jobs.drain(timeout=10)
        self.assertTrue(any('explode' in line for line in logged.output),
                        'a failed job was swallowed without a word')

        survivor = []
        jobs.enqueue(survivor.append, 'still here', label='survivor')
        jobs.drain(timeout=10)
        self.assertEqual(
            survivor, ['still here'],
            'one failing job cost the pool a worker for good')

    def test_the_queue_is_emptied_of_a_job_that_failed(self):
        def explode():
            raise RuntimeError('deliberate')

        with self.assertLogs('api.jobs', level='ERROR'):
            jobs.enqueue(explode, label='explode')
            jobs.drain(timeout=10)
        self.assertEqual(
            jobs.pending(), 0,
            'a failed job was still counted against the queue limit')

    @override_settings(BACKGROUND_QUEUE_LIMIT=1)
    def test_an_overflowing_queue_runs_inline_rather_than_dropping_the_work(self):
        release = threading.Event()
        self.addCleanup(release.set)
        done = []

        jobs.enqueue(release.wait, 10, label='blocker')
        with self.assertLogs('api.jobs', level='WARNING') as logged:
            jobs.enqueue(done.append, 'overflow', label='overflow')

        self.assertEqual(
            done, ['overflow'],
            'work was dropped instead of falling back to the request thread')
        self.assertTrue(any('queue is full' in line for line in logged.output))
        release.set()


@override_settings(**THREADED)
class ThreadedDatabaseJobTest(ThreadedSqliteMixin, TransactionTestCase):
    """A job that touches the database, on its own connection.

    ``TransactionTestCase`` rather than ``TestCase``: the pool thread is outside
    the case's transaction, so under ``TestCase`` it would either see nothing or
    see rows the rollback then takes away.
    """

    def setUp(self):
        super().setUp()
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student')
        self.profile = StudentProfile.objects.create(
            user=user, student_id='2022-00111', course='BSCS', year_level=2)

    def tearDown(self):
        self.settle()

    def test_a_queued_message_reaches_the_inbox(self):
        notify.queue_email('ana@bipsu.edu.ph', 'Subject', 'Body')
        self.assertTrue(self.settle(), 'the mail job never finished')
        self.assertEqual([m.subject for m in mail.outbox], ['Subject'])

    def test_the_portal_notice_is_written_before_the_caller_is_released(self):
        in_app, emailed = notify.notify(
            self.profile, 'Decided', 'Your application was approved.')
        self.assertTrue(in_app)
        self.assertIsNone(
            emailed, 'a queued message reported an outcome nobody had yet')
        self.assertEqual(
            Notification.objects.filter(student=self.profile).count(), 1,
            'the reliable half of the notification was queued as well')
        self.settle()
        self.assertEqual(len(mail.outbox), 1)


class InlineMailStaysInlineTest(TransactionTestCase):
    """The two sends whose answer somebody is shown must not be queued.

    Both report back in the response: the mail panel says whether the test
    message was accepted, and the account decision warns the office when the
    applicant could not be told. A queued send has no answer to give them.
    """

    @override_settings(**THREADED)
    def test_an_account_decision_reports_whether_it_reached_the_applicant(self):
        account = User.objects.create_user(
            username='ben@bipsu.edu.ph', email='ben@bipsu.edu.ph',
            password='pw', first_name='Ben', last_name='Cruz', role='student',
            verification_status='approved')
        _in_app, emailed = notify.account_decision(
            account, 'approved', 'Checked against the registrar list.')
        self.assertIs(
            emailed, True,
            'the office was left guessing whether the applicant was emailed')
        self.assertEqual(len(mail.outbox), 1,
                         'the message had not gone out when the office was told '
                         'it had')
