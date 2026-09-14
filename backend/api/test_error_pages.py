from django.template import loader
from django.test import Client, TestCase, override_settings

from .error_views import csrf_failure


class CsrfFailurePageTest(TestCase):
    def setUp(self):
        self.c = Client(enforce_csrf_checks=True)

    def test_a_missing_token_gets_the_written_page_not_djangos(self):
        r = self.c.post('/login/', {'email': 'a@b.ph', 'password': 'pw'})
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, 'That form is no longer valid', status_code=403)
        self.assertNotContains(r, 'CSRF verification failed', status_code=403)
        self.assertNotContains(r, 'Request aborted', status_code=403)

    def test_it_says_what_actually_causes_this(self):
        r = self.c.post('/login/', {'email': 'a@b.ph', 'password': 'pw'})
        self.assertContains(r, 'long enough for your sign-in to expire', status_code=403)
        self.assertContains(r, 'blocking cookies', status_code=403)

    def test_it_offers_a_way_out(self):
        r = self.c.post('/login/', {'email': 'a@b.ph', 'password': 'pw'})
        self.assertContains(r, 'Sign in again', status_code=403)

    @override_settings(DEBUG=False)
    def test_djangos_own_reason_is_kept_from_the_public(self):
        r = csrf_failure(_bare_request(), reason='CSRF cookie not set.')
        self.assertNotIn(b'CSRF cookie not set', r.content)

    @override_settings(DEBUG=True)
    def test_and_shown_to_whoever_is_debugging(self):
        r = csrf_failure(_bare_request(), reason='CSRF cookie not set.')
        self.assertIn(b'CSRF cookie not set', r.content)


class ServerErrorPageTest(TestCase):
    def test_it_renders_with_nothing_behind_it(self):
        html = loader.render_to_string('errors/500.html', {})
        self.assertIn('Something broke at our end', html)
        self.assertIn('BiPSU SRMS', html)


class NotFoundPageTest(TestCase):
    @override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'])
    def test_an_unknown_address_gets_the_written_page(self):
        r = Client().get('/no-such-page/')
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, 'That page is not here', status_code=404)


def _bare_request():
    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory
    req = RequestFactory().post('/login/')
    req.user = AnonymousUser()
    return req
