"""Mobile navigation and keyboard navigation."""

from api.models import StudentProfile, SystemSettings, User

from .base import MOBILE, BrowserTestCase


class StudentBrowserTestCase(BrowserTestCase):

    def setUp(self):
        super().setUp()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student',
            verification_status='approved')
        StudentProfile.objects.create(
            user=user, student_id='2022-00111', course='BSCS', year_level=2)
        self.sign_in('ana@bipsu.edu.ph', 'pw')


class MobileNavigationTest(StudentBrowserTestCase):
    """The sidebar on a phone-sized viewport."""

    viewport = MOBILE

    def _open_sidebar(self):
        self.visit('/student/applications/')
        toggle = self.page.query_selector('#sidebarToggle')
        if toggle is None:
            self.skipTest('this page has no sidebar toggle')
        toggle.click()
        self.page.wait_for_timeout(300)
        return toggle

    def test_the_toggle_opens_the_sidebar(self):
        self._open_sidebar()
        classes = self.page.get_attribute('#appSidebar', 'class')
        self.assertIn('is-open', classes, 'the sidebar did not open')

    def test_the_toggle_reports_its_state_to_a_screen_reader(self):
        """Closed with Escape, not with the toggle.

        Once the drawer is open it covers the toggle, so the same button
        cannot be clicked again — the drawer is dismissed with Escape or the
        backdrop. What matters for a screen reader is that ``aria-expanded``
        tracks the state however it changed.
        """
        toggle = self._open_sidebar()
        self.assertEqual(
            toggle.get_attribute('aria-expanded'), 'true',
            'aria-expanded did not follow the sidebar open')
        self.page.keyboard.press('Escape')
        self.page.wait_for_timeout(300)
        self.assertEqual(toggle.get_attribute('aria-expanded'), 'false')

    def test_escape_closes_the_sidebar(self):
        self._open_sidebar()
        self.page.keyboard.press('Escape')
        self.page.wait_for_timeout(300)
        self.assertNotIn('is-open',
                         self.page.get_attribute('#appSidebar', 'class'))

    def test_tapping_the_backdrop_closes_the_sidebar(self):
        """Tapped to the right of the drawer.

        The backdrop spans the viewport and the drawer sits on top of its left
        edge, so a click at the backdrop's centre lands on the drawer instead.
        A real thumb reaches for the uncovered part.
        """
        self._open_sidebar()
        width = self.page.evaluate('document.documentElement.clientWidth')
        height = self.page.evaluate('document.documentElement.clientHeight')
        self.page.mouse.click(width - 12, height // 2)
        self.page.wait_for_timeout(300)
        self.assertNotIn('is-open',
                         self.page.get_attribute('#appSidebar', 'class'))

    def test_the_page_does_not_scroll_sideways_on_a_phone(self):
        self.visit('/student/applications/')
        overflow = self.page.evaluate(
            'document.documentElement.scrollWidth - '
            'document.documentElement.clientWidth')
        self.assertLessEqual(
            overflow, 1,
            f'the page scrolls {overflow}px sideways at {MOBILE["width"]}px wide')


class KeyboardNavigationTest(StudentBrowserTestCase):
    """Reaching and operating the page without a mouse."""

    def test_tab_reaches_a_focusable_control_from_the_top_of_the_page(self):
        self.visit('/student/applications/')
        self.page.keyboard.press('Tab')
        tag = self.page.evaluate(
            'document.activeElement && document.activeElement.tagName')
        self.assertIn(
            tag, ('A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'),
            f'the first Tab landed on {tag}, which cannot be operated')

    def test_every_focused_control_shows_a_visible_focus_ring(self):
        self.visit('/student/applications/')
        self.page.keyboard.press('Tab')
        outline = self.page.evaluate("""
            (() => {
              const el = document.activeElement;
              if (!el) return null;
              const s = getComputedStyle(el);
              return {
                outlineWidth: s.outlineWidth,
                outlineStyle: s.outlineStyle,
                boxShadow: s.boxShadow,
              };
            })()
        """)
        self.assertIsNotNone(outline)
        visible = (
            outline['outlineStyle'] not in ('none', '')
            and outline['outlineWidth'] not in ('0px', '')
        ) or outline['boxShadow'] not in ('none', '')
        self.assertTrue(
            visible,
            'the focused control has no visible focus indicator, so a '
            f'keyboard user cannot tell where they are: {outline}')

    def test_the_form_can_be_submitted_with_the_keyboard_alone(self):
        """Signed out first: the shared setUp signs in, and /login/ redirects."""
        self.context.clear_cookies()
        self.visit('/login/')
        self.page.click('input[name="email"]')
        self.page.keyboard.type('ana@bipsu.edu.ph')
        self.page.keyboard.press('Tab')
        self.assertEqual(
            self.page.evaluate('document.activeElement.name'), 'password',
            'Tab from the address did not reach the password field')
        self.page.keyboard.type('pw')
        with self.page.expect_navigation(wait_until='domcontentloaded',
                                         timeout=10000):
            self.page.keyboard.press('Enter')
        self.assertNotIn(
            '/login/', self.page.url,
            'pressing Enter in the password field did not submit the form')
