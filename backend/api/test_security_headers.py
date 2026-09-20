"""The browser policy headers, asserted on real responses.

Asserting that a directive appears in ``settings.CONTENT_SECURITY_POLICY``
would pass with the middleware unregistered, so every case here reads a
header off a response the test suite actually fetched.
"""

from django.test import Client, TestCase, override_settings

from api.middleware import _csp_value, _permissions_value


def _directives(value):
    """A CSP header value as ``{directive: [sources]}``."""
    parsed = {}
    for part in value.split(';'):
        pieces = part.split()
        if pieces:
            parsed[pieces[0]] = pieces[1:]
    return parsed


class SecurityHeaderTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_an_html_page_carries_a_content_security_policy(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Content-Security-Policy', response)

    def test_the_policy_forbids_plugins_and_foreign_form_targets(self):
        directives = _directives(
            self.client.get('/login/')['Content-Security-Policy'])
        self.assertEqual(directives['object-src'], ["'none'"])
        self.assertEqual(directives['form-action'], ["'self'"])
        self.assertEqual(directives['base-uri'], ["'self'"])
        self.assertEqual(directives['frame-ancestors'], ["'self'"])

    def test_the_only_foreign_script_host_is_the_chart_cdn(self):
        directives = _directives(
            self.client.get('/login/')['Content-Security-Policy'])
        foreign = [source for source in directives['script-src']
                   if source.startswith('http')]
        self.assertEqual(foreign, ['https://cdn.jsdelivr.net'])

    def test_default_src_admits_nothing_from_another_origin(self):
        directives = _directives(
            self.client.get('/login/')['Content-Security-Policy'])
        self.assertEqual(directives['default-src'], ["'self'"])

    def test_the_page_denies_the_camera_microphone_and_location(self):
        header = self.client.get('/login/')['Permissions-Policy']
        for feature in ('camera', 'microphone', 'geolocation', 'payment', 'usb'):
            with self.subTest(feature=feature):
                self.assertIn(f'{feature}=()', header)

    def test_permissions_policy_uses_its_own_grammar_not_csps(self):
        header = self.client.get('/login/')['Permissions-Policy']
        self.assertIn('fullscreen=(self)', header)
        self.assertNotIn('fullscreen=((self))', header)
        self.assertNotIn(';', header)

    def test_a_spreadsheet_download_carries_no_document_policy(self):
        from django.http import HttpResponse

        from api.middleware import SecurityHeadersMiddleware

        sheet = HttpResponse(b'x', content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
        middleware = SecurityHeadersMiddleware(lambda request: sheet)
        response = middleware(self.client.request().wsgi_request)
        self.assertNotIn('Content-Security-Policy', response)
        self.assertNotIn('Permissions-Policy', response)

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_mode_sends_the_report_only_header(self):
        from django.http import HttpResponse

        from api.middleware import SecurityHeadersMiddleware

        page = HttpResponse('<p>x</p>', content_type='text/html')
        middleware = SecurityHeadersMiddleware(lambda request: page)
        response = middleware(self.client.request().wsgi_request)
        self.assertIn('Content-Security-Policy-Report-Only', response)
        self.assertNotIn('Content-Security-Policy', response)


class HstsTest(TestCase):

    def test_hsts_is_long_enough_to_mean_something(self):
        from config import settings as project_settings

        source = open(project_settings.__file__, encoding='utf-8').read()
        self.assertIn("'SECURE_HSTS_SECONDS', '31536000'", source)
        self.assertNotIn("'SECURE_HSTS_SECONDS', '3600'", source)


class PolicySerialisationTest(TestCase):

    def test_an_empty_allowlist_denies_rather_than_omits(self):
        self.assertEqual(_permissions_value({'camera': []}), 'camera=()')

    def test_a_valueless_csp_directive_is_written_bare(self):
        self.assertEqual(
            _csp_value({'upgrade-insecure-requests': []}),
            'upgrade-insecure-requests')
