"""Shared setup for the browser tests.

These run against a real browser and a real server, because the behaviour they
cover — a dialog opening, a table filtering, a sidebar closing on Escape —
lives in JavaScript that no Django test can execute.

They are kept outside the ``api`` package on purpose, so ``manage.py test api``
stays runnable on a machine with no browser installed. Run them with::

    python manage.py test tests_browser

If Playwright is missing the whole suite skips with an instruction rather than
erroring, so a reviewer who only wants the backend tests is not blocked.
"""

import os
import unittest

os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')
"""Playwright's synchronous API runs its own event loop in this process.

Django sees a running loop and refuses every ORM call with
``SynchronousOnlyOperation``, even though nothing here is actually async — the
loop belongs to the browser driver, not to a server handling requests. This
flag tells Django the calls are safe, and it has to be set before the first
one, which is why it sits above the Django imports rather than in ``setUp``.

It is scoped to this package. The application never sets it.
"""

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False

SKIP_REASON = (
    'Playwright is not installed. Run:\n'
    '    pip install -r requirements-dev.txt\n'
    '    python -m playwright install chromium'
)

MOBILE = {'width': 390, 'height': 844}
DESKTOP = {'width': 1440, 'height': 900}


def _plain_static():
    """The project's storages, with the static one swapped for the plain backend.

    ``STORAGES`` has to be overridden whole, so the ``default`` media backend
    is carried across explicitly. Dropping it makes Django raise
    ``InvalidStorageError`` the moment a page touches a file field, which
    turns every profile page into a 500 and every test here into a mystery.
    """
    from django.conf import settings as project_settings

    storages = dict(project_settings.STORAGES)
    storages['staticfiles'] = {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    }
    return storages


@override_settings(STORAGES=_plain_static())
@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, SKIP_REASON)
class BrowserTestCase(StaticLiveServerTestCase):
    """A live server, a Chromium page, and helpers for signing in.

    One browser is started per class and a fresh context per test, which keeps
    the cost of launching Chromium off every individual case while still giving
    each one an empty cookie jar.

    Static files are served unhashed. The project stores them through a
    manifest backend that rewrites ``{% static %}`` to a digest filename, and
    those names exist only under ``STATIC_ROOT`` after ``collectstatic``. The
    live-server handler serves from the source tree instead, so every
    stylesheet and script 404s and the page arrives with no behaviour at all —
    which makes every test here pass or fail for the wrong reason. Swapping in
    the plain backend keeps the URLs and the files in step without requiring a
    build step before the suite.
    """

    viewport = DESKTOP

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._playwright = sync_playwright().start()
        cls.browser = cls._playwright.chromium.launch(
            headless=os.environ.get('HEADED') != '1')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._playwright.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.context = self.browser.new_context(viewport=self.viewport)
        self.page = self.context.new_page()
        self.console_errors = []
        self.page.on('pageerror', lambda exc: self.console_errors.append(str(exc)))
        self.page.on('console', self._note_console)

    def tearDown(self):
        self.context.close()
        super().tearDown()

    RESOURCE_NOISE = (
        'Failed to load resource',
        'net::ERR_',
        'favicon',
    )

    def _note_console(self, message):
        """Record script errors, ignoring failed resource loads.

        The live-server test harness serves static files from the source tree
        rather than from the hashed manifest the templates ask for, so a run
        produces a steady stream of 404s for CSS and JS. Those are network
        events, not script errors, and letting them into the assertion would
        bury the one line that matters — an actual exception in page code.
        """
        if message.type != 'error':
            return
        text = message.text or ''
        if any(noise in text for noise in self.RESOURCE_NOISE):
            return
        self.console_errors.append(text)

    def visit(self, path):
        """Open a path and wait until the page is actually operable.

        Every page paints a full-screen loading skeleton and removes it once
        fonts have settled. Until then the skeleton sits over the content, and
        Playwright refuses to click anything beneath it — the click times out
        and the test reads as a broken feature rather than a page that had not
        finished arriving.
        """
        self.page.goto(f'{self.live_server_url}{path}')
        self.page.wait_for_load_state('domcontentloaded')
        self.settle()
        return self.page

    def settle(self, timeout=6000):
        """Wait for the loading skeleton to clear."""
        try:
            self.page.wait_for_function(
                "!document.documentElement.classList.contains('is-loading')",
                timeout=timeout)
        except Exception:
            pass
        try:
            self.page.wait_for_selector('.page-skeleton, .page-loader',
                                        state='detached', timeout=timeout)
        except Exception:
            pass

    def sign_in(self, email, password):
        """Sign in through the real form rather than by forcing a session."""
        self.visit('/login/')
        self.page.fill('input[name="email"]', email)
        self.page.fill('input[name="password"]', password)
        self.page.click('button[type="submit"]')
        self.page.wait_for_load_state('domcontentloaded')
        self.settle()

    def assertNoConsoleErrors(self):
        """Fail if the page logged a script error while the test ran.

        Worth asserting on every page: a JavaScript exception leaves the page
        looking correct while its behaviour is silently gone, which is exactly
        the class of fault these tests exist to catch.
        """
        self.assertEqual(
            self.console_errors, [],
            f'the page reported script errors: {self.console_errors}')
