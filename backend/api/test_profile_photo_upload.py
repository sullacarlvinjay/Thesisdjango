import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATES = Path(settings.BASE_DIR) / 'templates'

PHOTO_INPUT = re.compile(r'<input[^>]*onchange="this\.form\.submit\(\)"[^>]*>')
FORM_OPEN = re.compile(r'<form\b[^>]*>')
FORM_CLOSE = re.compile(r'</form>')

PROFILE_PAGES = (
    'student/profile.html',
    'nsu_staff/profile.html',
    'partner/profile.html',
    'vpsea/profile.html',
)


def _owns_a_form(html, control):
    """Whether a control can reach a form, by nesting or by ``form=``.

    ``this.form`` is ``null`` for a control that is inside no form and names
    none, and reading ``.submit()`` off null throws. The control still renders
    and still opens a file picker, so the page looks completely healthy while
    choosing a photo does nothing at all.
    """
    if 'form=' in control:
        return True
    start = html.index(control)
    opens = len(FORM_OPEN.findall(html[:start]))
    closes = len(FORM_CLOSE.findall(html[:start]))
    return opens > closes


class AvatarUploadReachesAFormTest(SimpleTestCase):
    """Every portal's photo picker must be able to submit something.

    The student page had the picker in the page header and the form two
    hundred lines below it, so the control was inside no form. Nothing failed
    loudly: the picker opened, a file was chosen, and the page sat there.
    """

    def test_every_photo_picker_can_reach_its_form(self):
        for page in PROFILE_PAGES:
            path = TEMPLATES / page
            if not path.exists():
                continue
            html = path.read_text(encoding='utf-8')
            for control in PHOTO_INPUT.findall(html):
                with self.subTest(page=page):
                    self.assertTrue(
                        _owns_a_form(html, control),
                        f'{page}: this control calls this.form.submit() but '
                        'sits in no form and names none, so choosing a file '
                        'throws instead of uploading')

    def test_the_student_picker_names_the_form_it_belongs_to(self):
        html = (TEMPLATES / 'student/profile.html').read_text(encoding='utf-8')
        self.assertIn('id="studentProfileForm"', html)
        self.assertIn('form="studentProfileForm"', html)
