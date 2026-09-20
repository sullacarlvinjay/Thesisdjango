import json

from django.test import Client, TestCase


class HealthEndpointTest(TestCase):
    """``/healthz/`` is polled to keep the container awake, so it must be cheap.

    The deployment sleeps after about fifteen minutes idle and then makes the
    next visitor wait roughly fifty seconds. An external monitor hitting this
    every ten minutes absorbs that cost instead. Because it is polled rather
    than visited, it must not query anything: a check that touched the database
    would add load on every poll and would call the process dead whenever the
    database merely hiccuped.
    """

    def setUp(self):
        self.c = Client()

    def test_it_answers_without_signing_in(self):
        r = self.c.get('/healthz/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.content)['status'], 'ok')

    def test_it_touches_no_database(self):
        with self.assertNumQueries(0):
            self.c.get('/healthz/')

    def test_it_is_never_cached(self):
        self.assertIn('no-store', self.c.get('/healthz/')['Cache-Control'])

    def test_it_reports_how_long_the_process_has_been_up(self):
        body = json.loads(self.c.get('/healthz/').content)
        self.assertIn('uptime_seconds', body)
        self.assertGreaterEqual(body['uptime_seconds'], 0)


class ReadinessEndpointTest(TestCase):
    """``/readyz/`` is the opposite: it does check the dependencies."""

    def setUp(self):
        self.c = Client()

    def test_it_reports_each_dependency_by_name(self):
        body = json.loads(self.c.get('/readyz/').content)
        self.assertEqual(body['status'], 'ok')
        self.assertIn('database', body['checks'])
        self.assertIn('cache', body['checks'])

    def test_a_broken_dependency_gives_503_and_names_itself(self):
        from unittest.mock import patch
        with patch('django.db.connection.cursor', side_effect=RuntimeError('down')):
            r = self.c.get('/readyz/')
        self.assertEqual(r.status_code, 503)
        body = json.loads(r.content)
        self.assertEqual(body['status'], 'degraded')
        self.assertFalse(body['checks']['database']['ok'])
        self.assertEqual(
            body['checks']['database']['error'], 'RuntimeError',
            'the failing dependency was not named, so the cause has to be '
            'guessed from logs')
