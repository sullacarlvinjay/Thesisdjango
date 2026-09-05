"""Registration says which fields it can do without.

The form asks for a great deal and refuses a registration over almost none of
it. Every field it does not need now carries an "Optional" marker, which makes
the form finishable in one sitting instead of one long guess.

**The marker only means anything if it is applied consistently.** If some
optional fields carry it and others do not, its absence stops meaning
"required" and the whole device is noise — so this checks both directions:
every field register_view can refuse a registration over is unmarked, and
every field it cannot is marked.

The one exception is checkboxes. An unticked box is an answer rather than an
omission, and "Optional" beside one reads as a question about the box.
"""
import re

from django.test import Client, TestCase

from api.models import SystemSettings

# What register_view actually refuses a registration over. Five for everyone,
# plus the student number; the conditional three are marked required by
# static/js/register-scholarship.js only once the award they belong to is
# declared, and disability_type_other only once "Other" is chosen.
ALWAYS_REQUIRED = {'first_name', 'last_name', 'email', 'password', 'confirm_password'}
STUDENT_REQUIRED = {'student_id'}
CONDITIONALLY_REQUIRED = {'disability_type_other', 'scholarship_type',
                          'award_tier', 'proof_document'}
CHECKBOXES = {'has_scholarship', 'is_tes_beneficiary'}

NEVER_MARKED = ALWAYS_REQUIRED | STUDENT_REQUIRED | CONDITIONALLY_REQUIRED | CHECKBOXES

FIELD = re.compile(r'<(?:input|select|textarea)\b[^>]*\bname="([^"]+)"')
TAG = 'label-optional'


def fields(html):
    """Every posted field, with its label line and whether it is marked."""
    lines = html.splitlines()
    out = {}
    for i, line in enumerate(lines):
        match = FIELD.search(line)
        if not match:
            continue
        name = match.group(1)
        if name in ('csrfmiddlewaretoken', 'account_type'):
            continue
        label = ''
        for j in range(i, max(i - 8, -1), -1):
            # The first <label> above the field, opened-and-closed or not. A
            # checkbox's label wraps it across several lines, so requiring a
            # closer on the same line walks straight past it and picks up the
            # previous field's label instead.
            if '<label' in lines[j]:
                label = lines[j]
                break
        out[name] = {'marked': TAG in label,
                     'required': 'required' in match.group(0) or ' required ' in line}
    return out


class RegistrationOptionalMarkersTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.html = Client().get('/register/').content.decode()

    # ── Both directions of the same rule ────────────────────────────────────

    def test_every_optional_field_is_marked(self):
        """A field the form does not need, unmarked, is a field somebody fills
        in because they assumed they had to."""
        unmarked = sorted(name for name, f in fields(self.html).items()
                          if name not in NEVER_MARKED and not f['marked'])
        self.assertEqual(unmarked, [],
                         'these are optional but say nothing about it: ' + ', '.join(unmarked))

    def test_no_required_field_is_marked_optional(self):
        """The direction that would actively mislead — a student skips it, and
        the form comes back refused."""
        wrong = sorted(name for name in NEVER_MARKED
                       if fields(self.html).get(name, {}).get('marked'))
        self.assertEqual(wrong, [],
                         'these are required but marked Optional: ' + ', '.join(wrong))

    # ── The marker means what it says ───────────────────────────────────────

    def test_the_browser_enforces_exactly_what_is_unmarked(self):
        """`required` and the absence of the marker have to agree, or the form
        tells the reader one thing and the browser another."""
        found = fields(self.html)
        for name in ALWAYS_REQUIRED | STUDENT_REQUIRED:
            with self.subTest(field=name):
                self.assertTrue(found[name]['required'],
                                f'{name} reads as required but the browser does not ask for it')

    def test_student_id_is_required_in_the_browser_too(self):
        """It always was on the server — 'Student ID is required.' — while the
        input let the form submit without it."""
        self.assertTrue(fields(self.html)['student_id']['required'])

    def test_a_registration_without_a_student_id_is_still_refused(self):
        """The server rule the attribute now matches, unchanged."""
        from api.models import User

        html = Client().post('/register/', {
            'account_type': 'student', 'first_name': 'Ana', 'last_name': 'Reyes',
            'email': 'ana@gmail.com', 'password': 'pw12345',
            'confirm_password': 'pw12345', 'course': 'BSCS', 'year_level': '1',
        }).content.decode()
        self.assertIn('Student ID is required', html)
        self.assertFalse(User.objects.filter(email='ana@gmail.com').exists())

    # ── One vocabulary ──────────────────────────────────────────────────────

    def test_the_form_marks_optional_one_way_only(self):
        """It used to say "(optional)" in two places and "(if applicable)" in a
        third. Three spellings of one idea read as three different rules."""
        self.assertNotIn('(optional)', self.html)
        self.assertNotIn('(if applicable)', self.html)

    def test_a_marked_field_is_never_also_required(self):
        """The contradiction the two lists above exist to prevent, checked
        against the rendered page rather than against the lists."""
        contradictory = sorted(name for name, f in fields(self.html).items()
                               if f['marked'] and f['required'])
        self.assertEqual(contradictory, [])
