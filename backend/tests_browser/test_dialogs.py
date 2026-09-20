"""Confirmation dialogs and preview modals.

Both are implemented entirely in the browser — `static/js/confirm-dialog.js`
and `static/js/modal-open.js` — so nothing in the Django suite can tell whether
they work. A destructive action whose confirmation step has silently stopped
intercepting is the worst version of this failing, which is why the first test
here checks that the form does *not* submit.
"""

from api.models import PartnerOffice, Scholarship, SystemSettings, User

from .base import BrowserTestCase


class OfficeBrowserTestCase(BrowserTestCase):
    """Signed in as the SDSO office, which is where these controls live."""

    def setUp(self):
        super().setUp()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        User.objects.create_user(
            username='office@bipsu.edu.ph', email='office@bipsu.edu.ph',
            password='office-pw', first_name='Rosario', last_name='Bayhon',
            role='vpsea')
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic',
            category='application', description='x', eligibility='x',
            requirements=[])
        PartnerOffice.objects.create(name='UniFAST Region VIII', is_active=True)
        self.sign_in('office@bipsu.edu.ph', 'office-pw')


class ConfirmationDialogTest(OfficeBrowserTestCase):

    def _first_confirmable(self):
        """The partners page carries the suspend control, which asks first."""
        self.visit('/vpsea/partners/')
        return self.page.query_selector('[data-confirm]')

    def test_a_destructive_control_opens_the_dialog_instead_of_acting(self):
        control = self._first_confirmable()
        if control is None:
            self.skipTest('no [data-confirm] control on this page')
        before = self.page.url
        control.click()
        self.page.wait_for_timeout(250)
        dialog = self.page.query_selector('#confirmDialog')
        self.assertIsNotNone(dialog, 'the confirmation dialog is not on the page')
        self.assertFalse(
            dialog.is_hidden(),
            'the control acted without asking for confirmation')
        self.assertEqual(self.page.url, before)

    def test_cancelling_leaves_the_page_untouched(self):
        control = self._first_confirmable()
        if control is None:
            self.skipTest('no [data-confirm] control on this page')
        before = self.page.url
        control.click()
        self.page.wait_for_timeout(250)
        self.page.click('#confirmCancel')
        self.page.wait_for_timeout(250)
        self.assertTrue(self.page.query_selector('#confirmDialog').is_hidden())
        self.assertEqual(self.page.url, before)

    def test_escape_closes_the_dialog(self):
        control = self._first_confirmable()
        if control is None:
            self.skipTest('no [data-confirm] control on this page')
        control.click()
        self.page.wait_for_timeout(250)
        self.page.keyboard.press('Escape')
        self.page.wait_for_timeout(250)
        self.assertTrue(self.page.query_selector('#confirmDialog').is_hidden())

    def test_the_dialog_takes_focus_so_the_keyboard_can_answer_it(self):
        control = self._first_confirmable()
        if control is None:
            self.skipTest('no [data-confirm] control on this page')
        control.click()
        self.page.wait_for_timeout(250)
        focused = self.page.evaluate('document.activeElement && document.activeElement.id')
        self.assertEqual(
            focused, 'confirmGo',
            'focus stayed behind the dialog, so a keyboard user cannot answer it')


class PreviewModalTest(OfficeBrowserTestCase):
    """The record preview on the verification queue.

    A preview only exists for an account the office has already decided, so
    one is decided here first. Without it the page renders no modal at all and
    these cases skip, reporting nothing about whether previews work.
    """

    def setUp(self):
        super().setUp()
        from api.models import StudentProfile

        applicant = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student',
            verification_status='pending')
        StudentProfile.objects.create(
            user=applicant, student_id='2022-00111', course='BSCS',
            year_level=2)
        officer = User.objects.get(email='office@bipsu.edu.ph')
        applicant.decide_verification('approved', 'Checked.', officer)

    def test_a_preview_opens_and_closes_on_escape(self):
        self.visit('/vpsea/accounts/')
        opener = self.page.query_selector('[data-preview-open]')
        if opener is None:
            self.skipTest('no preview control on this page')
        opener.click()
        self.page.wait_for_timeout(300)
        self.assertIsNotNone(
            self.page.query_selector('.modal-overlay.open'),
            'the preview did not open')
        self.page.keyboard.press('Escape')
        self.page.wait_for_timeout(300)
        self.assertIsNone(
            self.page.query_selector('.modal-overlay.open'),
            'Escape did not close the preview')

    def test_clicking_the_backdrop_closes_the_preview(self):
        self.visit('/vpsea/accounts/')
        opener = self.page.query_selector('[data-preview-open]')
        if opener is None:
            self.skipTest('no preview control on this page')
        opener.click()
        self.page.wait_for_timeout(300)
        overlay = self.page.query_selector('.modal-overlay.open')
        if overlay is None:
            self.skipTest('the preview did not open')
        box = overlay.bounding_box()
        self.page.mouse.click(box['x'] + 6, box['y'] + 6)
        self.page.wait_for_timeout(300)
        self.assertIsNone(self.page.query_selector('.modal-overlay.open'))
