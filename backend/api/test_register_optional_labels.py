"""Registration says which fields it can do without, and there are seven.

The form asks for the whole student record and now refuses a registration over
nearly all of it. What stays optional is the short list of questions a truthful
person can have no answer to — a suffix most people do not have, an indigenous
group few belong to, an award number not every letter carries, two certificates
the form itself says can be uploaded later, and two boxes for anything else the
office should know. Those seven carry an "Optional" marker; nothing else does.

Seven *questions*, not seven inputs. The form asks for a scholarship the student
already holds up to three times — some hold two — so four of the names below
appear once per Scholarship Data card. Asking a question three times does not
make it three questions, and the rule being checked is about questions.

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
from api.student_views import DECLARATION_SLOTS


def per_card(*names):
    """Each name as it is posted from every Scholarship Data card.

    Read off DECLARATION_SLOTS rather than spelled out, so adding or removing a
    card cannot leave this file describing a form that no longer exists.
    """
    return {f'{name}{slot}' for name in names for slot in DECLARATION_SLOTS}


# What register_view actually refuses a registration over — see the lists it
# reads from, at the head of api/student_views.py's registration section.
#
# The conditional ones are marked required by static/js/register-scholarship.js
# only once the award they belong to is declared, and disability_type_other
# only once "Other" is chosen. Both halves of the form declare an award somebody
# already holds, so both have a proof: proof_document on the student's,
# staff_proof_document on the staff's.
ALWAYS_REQUIRED = {'first_name', 'last_name', 'middle_name', 'email',
                   'contact_number', 'password', 'confirm_password'}
STUDENT_REQUIRED = {
    'student_id',
    'date_of_birth', 'gender', 'birth_place', 'civil_status', 'disability_type',
    'barangay', 'municipality', 'province',
    'school', 'course', 'year_level',
    'elementary', 'highschool', 'last_school',
    # Two of the four groups the Affirmative Action programme is for. Required
    # of every student rather than only of applicants — see
    # api/affirmative_ranking.py, which turns on the difference between an
    # answered "no" and a question nobody asked.
    'highschool_is_public', 'is_from_depressed_area',
    'family_income',
    'shs_gpa', 'suc_exam_score', 'suc_exam_total',
    'citizenship', 'household_size', 'year_first_enrolled',
    'is_listahanan_household', 'is_4ps_beneficiary',
    'is_solo_parent_dependent', 'has_previous_degree',
}
STAFF_REQUIRED = {'school_id', 'staff_school', 'department', 'position'}
CONDITIONALLY_REQUIRED = ({'disability_type_other', 'staff_proof_document'}
                          | per_card('scholarship_type', 'award_tier',
                                     'proof_document'))
# A card after the first carries a hidden input saying it was used at all. It is
# neither asked nor answered, so it belongs with the boxes rather than with
# anything a marker could describe.
CHECKBOXES = ({'has_staff_scholarship', 'is_tes_beneficiary'}
              | per_card('has_scholarship'))

NEVER_MARKED = (ALWAYS_REQUIRED | STUDENT_REQUIRED | STAFF_REQUIRED
                | CONDITIONALLY_REQUIRED | CHECKBOXES)

# The seven, named rather than derived, so that moving a field out of the
# required lists cannot quietly move it in here as well. Two of them are asked
# once per Scholarship Data card, which is why they go through per_card.
OPTIONAL = ({'suffix', 'indigenous_group',
             'shs_gpa_cert', 'suc_exam_cert', 'staff_notes'}
            | per_card('award_number', 'notes'))

FIELD = re.compile(r'<(?:input|select|textarea)\b[^>]*?\bname="([^"]+)"[^>]*?>')
TAG = 'label-optional'


def fields(html):
    """Every posted field, with its label line and whether it is marked.

    The whole opening tag is read rather than the line the name happens to sit
    on: half of these wrap across two lines, and `required` lands on whichever
    of them has room for it.
    """
    lines = html.splitlines()
    out = {}
    for match in FIELD.finditer(html):
        name = match.group(1)
        if name in ('csrfmiddlewaretoken', 'account_type'):
            continue
        i = html.count('\n', 0, match.start())
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
                     'required': re.search(r'\brequired\b', match.group(0)) is not None}
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
        for name in ALWAYS_REQUIRED | STUDENT_REQUIRED | STAFF_REQUIRED:
            with self.subTest(field=name):
                self.assertTrue(found[name]['required'],
                                f'{name} reads as required but the browser does not ask for it')

    def test_the_optional_seven_are_exactly_the_marked_ones(self):
        """Named and derived have to agree, or one of the two lists is stale."""
        marked = {name for name, f in fields(self.html).items() if f['marked']}
        self.assertEqual(marked, OPTIONAL)

    def test_every_scholarship_card_marks_the_same_two_questions(self):
        """The rule has to survive the second and third cards.

        They are rendered by one loop, so a marker dropped from the loop body
        goes from every card at once — and the card a student reaches only when
        they hold two awards is the one nobody looks at."""
        found = fields(self.html)
        for slot in DECLARATION_SLOTS:
            for name in (f'award_number{slot}', f'notes{slot}'):
                with self.subTest(field=name):
                    self.assertIn(name, found, f'{name} is not on the form at all')
                    self.assertTrue(found[name]['marked'],
                                    f'{name} is optional but says nothing about it')

    def test_a_dropdown_that_opens_on_an_answer_is_not_a_required_question(self):
        """`required` on a select whose first option carries a value does
        nothing — the browser sees something chosen and lets the form go. Year
        Level opened on 1st Year and posted it for anybody who never looked."""
        # staff_school is not on this list: it is a typed field over a
        # <datalist> now, and an empty text input is exactly what `required`
        # does catch. See api/test_staff_school_units.py.
        for name in ('year_level', 'gender', 'civil_status', 'citizenship',
                     'disability_type', 'is_listahanan_household',
                     'is_4ps_beneficiary', 'is_solo_parent_dependent',
                     'has_previous_degree', 'school'):
            with self.subTest(field=name):
                select = re.search(r'<select[^>]*\bname="%s"[^>]*>(.*?)</select>' % name,
                                   self.html, re.S)
                first = re.search(r'<option[^>]*>', select.group(1)).group(0)
                self.assertIn('value=""', first,
                              f'{name} opens on an answer, so required cannot catch a blank')

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
