import re

from django.test import Client, TestCase

from api.models import SystemSettings
from api.student_views import DECLARATION_SLOTS


def per_card(*names):
    return {f'{name}{slot}' for name in names for slot in DECLARATION_SLOTS}


ALWAYS_REQUIRED = {'first_name', 'last_name', 'middle_name', 'email',
                   'contact_number', 'password', 'confirm_password',
                   'accept_terms'}
STUDENT_REQUIRED = {
    'student_id',
    'date_of_birth', 'gender', 'birth_place', 'civil_status', 'disability_type',
    'barangay', 'municipality', 'province',
    'school', 'course', 'year_level',
    'elementary', 'highschool', 'last_school',
    'highschool_is_public', 'is_from_depressed_area',
    'family_income',
    'shs_gpa', 'shs_gpa_cert', 'suc_exam_score', 'suc_exam_total',
    'suc_exam_cert', 'study_load',
    'citizenship', 'household_size', 'year_first_enrolled',
    'is_listahanan_household', 'is_4ps_beneficiary',
    'is_solo_parent_dependent', 'has_previous_degree',
}
STAFF_REQUIRED = {'school_id', 'staff_school', 'department', 'position',
                  'employment_status', 'designation'}
CONDITIONALLY_REQUIRED = ({'disability_type_other', 'staff_proof_document',
                           'years_of_service', 'date_of_regularization'}
                          | per_card('scholarship_type', 'award_tier',
                                     'proof_document',
                                     'staff_name', 'staff_employee_id',
                                     'relationship_to_staff'))
CHECKBOXES = ({'has_staff_scholarship', 'is_tes_beneficiary', 'terms_version'}
              | per_card('has_scholarship'))

NEVER_MARKED = (ALWAYS_REQUIRED | STUDENT_REQUIRED | STAFF_REQUIRED
                | CONDITIONALLY_REQUIRED | CHECKBOXES)

OPTIONAL = ({'suffix', 'indigenous_group', 'staff_notes'}
            | per_card('award_number', 'notes'))

FIELD = re.compile(r'<(?:input|select|textarea)\b[^>]*?\bname="([^"]+)"[^>]*?>')
TAG = 'label-optional'


def fields(html):
    lines = html.splitlines()
    out = {}
    for match in FIELD.finditer(html):
        name = match.group(1)
        if name in ('csrfmiddlewaretoken', 'account_type'):
            continue
        i = html.count('\n', 0, match.start())
        label = ''
        for j in range(i, max(i - 8, -1), -1):
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

    def test_every_optional_field_is_marked(self):
        unmarked = sorted(name for name, f in fields(self.html).items()
                          if name not in NEVER_MARKED and not f['marked'])
        self.assertEqual(unmarked, [],
                         'these are optional but say nothing about it: ' + ', '.join(unmarked))

    def test_no_required_field_is_marked_optional(self):
        wrong = sorted(name for name in NEVER_MARKED
                       if fields(self.html).get(name, {}).get('marked'))
        self.assertEqual(wrong, [],
                         'these are required but marked Optional: ' + ', '.join(wrong))

    def test_the_browser_enforces_exactly_what_is_unmarked(self):
        found = fields(self.html)
        for name in ALWAYS_REQUIRED | STUDENT_REQUIRED | STAFF_REQUIRED:
            with self.subTest(field=name):
                self.assertTrue(found[name]['required'],
                                f'{name} reads as required but the browser does not ask for it')

    def test_the_marked_fields_are_exactly_the_optional_ones(self):
        marked = {name for name, f in fields(self.html).items() if f['marked']}
        self.assertEqual(marked, OPTIONAL)

    def test_every_scholarship_card_marks_the_same_two_questions(self):
        found = fields(self.html)
        for slot in DECLARATION_SLOTS:
            for name in (f'award_number{slot}', f'notes{slot}'):
                with self.subTest(field=name):
                    self.assertIn(name, found, f'{name} is not on the form at all')
                    self.assertTrue(found[name]['marked'],
                                    f'{name} is optional but says nothing about it')

    def test_a_dropdown_that_opens_on_an_answer_is_not_a_required_question(self):
        for name in ('year_level', 'gender', 'civil_status', 'citizenship',
                     'disability_type', 'is_listahanan_household',
                     'is_4ps_beneficiary', 'is_solo_parent_dependent',
                     'has_previous_degree', 'school'):
            with self.subTest(field=name):
                select = re.search(rf'<select[^>]*\bname="{name}"[^>]*>(.*?)</select>',
                                   self.html, re.S)
                first = re.search(r'<option[^>]*>', select.group(1)).group(0)
                self.assertIn('value=""', first,
                              f'{name} opens on an answer, so required cannot catch a blank')

    def test_student_id_is_required_in_the_browser_too(self):
        self.assertTrue(fields(self.html)['student_id']['required'])

    def test_a_registration_without_a_student_id_is_still_refused(self):
        from api.models import User

        html = Client().post('/register/', {
            'account_type': 'student', 'first_name': 'Ana', 'last_name': 'Reyes',
            'email': 'ana@gmail.com', 'password': 'pw12345',
            'confirm_password': 'pw12345', 'course': 'BSCS', 'year_level': '1',
        }).content.decode()
        self.assertIn('Student ID is required', html)
        self.assertFalse(User.objects.filter(email='ana@gmail.com').exists())

    def test_the_form_marks_optional_one_way_only(self):
        self.assertNotIn('(optional)', self.html)
        self.assertNotIn('(if applicable)', self.html)

    def test_a_marked_field_is_never_also_required(self):
        contradictory = sorted(name for name, f in fields(self.html).items()
                               if f['marked'] and f['required'])
        self.assertEqual(contradictory, [])
