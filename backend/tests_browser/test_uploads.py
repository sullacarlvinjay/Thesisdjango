"""File upload through the real form control."""

import tempfile
from pathlib import Path

from api.models import StudentProfile, SystemSettings, User

from .base import BrowserTestCase


def _file(name, content=b'%PDF-1.4 test document', size=None):
    """Write a throwaway file and return its path."""
    path = Path(tempfile.mkdtemp()) / name
    path.write_bytes(content if size is None else b'0' * size)
    return str(path)


class UploadTest(BrowserTestCase):

    def setUp(self):
        super().setUp()
        settings_obj, _ = SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester',
                            'max_file_size_mb': 5})
        self.settings_obj = settings_obj
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student',
            verification_status='approved')
        StudentProfile.objects.create(
            user=user, student_id='2022-00111', course='BSCS', year_level=2)
        self.sign_in('ana@bipsu.edu.ph', 'pw')

    def _first_file_input(self, path):
        self.visit(path)
        return self.page.query_selector('input[type="file"]')

    def test_choosing_a_photo_submits_the_form(self):
        """The picker auto-submits, so the page navigates on selection.

        This is the case that was broken: the control sat outside every form,
        so ``this.form`` was null and choosing a photo threw instead of
        uploading. Nothing on screen said so — the picker opened, a file was
        chosen, and the page simply sat there.
        """
        self.visit('/student/profile/')
        control = self.page.query_selector('#photoInput')
        if control is None:
            self.skipTest('no photo picker on this page')

        with self.page.expect_navigation(wait_until='domcontentloaded',
                                         timeout=10000):
            control.set_input_files(_file('portrait.png'))
        self.settle()
        self.assertNotIn(
            "Cannot read properties of null", ' '.join(self.console_errors),
            'the photo picker cannot reach a form, so choosing a file threw')

    def test_the_photo_control_advertises_which_types_it_accepts(self):
        self.visit('/student/profile/')
        control = self.page.query_selector('#photoInput')
        if control is None:
            self.skipTest('no photo picker on this page')
        self.assertTrue(
            control.get_attribute('accept'),
            'the file control has no accept attribute, so the file picker '
            'offers every file on the machine including ones the server '
            'will reject')

    def test_an_oversized_file_is_refused_by_the_server_not_just_the_page(self):
        """Client-side size checks are a courtesy; the server has to enforce it.

        Driven through the browser rather than the test client on purpose: it
        proves the limit survives the real multipart round trip, which is the
        path an attacker would use after disabling the page's own check.
        """
        limit_mb = self.settings_obj.max_file_size_mb or 5
        self.visit('/student/profile/')
        control = self.page.query_selector(
            'input[type="file"]:not(#photoInput)')
        if control is None:
            self.skipTest('no ordinary file input on this page')
        self.page.evaluate("""
            () => document.querySelectorAll('input[type=file]')
                    .forEach(el => el.removeAttribute('accept'))
        """)
        control.set_input_files(
            _file('huge.pdf', size=(limit_mb + 2) * 1024 * 1024))
        submit = self.page.query_selector('button[type="submit"]')
        if submit is None:
            self.skipTest('no submit control on this page')
        submit.click()
        self.page.wait_for_load_state('domcontentloaded')
        self.settle()
        body = self.page.inner_text('body')
        self.assertNotIn(
            'Server Error', body,
            'an oversized upload produced a 500 instead of a message')
        self.assertTrue(
            'MB' in body or 'large' in body.lower() or 'limit' in body.lower(),
            'an oversized upload was neither refused nor explained')
