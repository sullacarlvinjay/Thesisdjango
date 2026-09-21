import re

from django.test import Client, TestCase

from api.fixtures_registration import a_staff_member, a_student
from api.models import SystemSettings, User

FORM_TAG = re.compile(r'<form\b[^>]*id="registerForm"[^>]*>')
STEP_LABEL = re.compile(r'data-step-label="([^"]+)"')
BANNER = re.compile(r'<div[^>]*\bdata-form-errors\b.*?</div>', re.S)
FLAGGED = re.compile(r'data-error-field="([^"]+)"')
CONTROL = re.compile(r'<(?:input|select|textarea)\b[^>]*?\bname="([^"]+)"')


def form_tag(html):
    return FORM_TAG.search(html).group(0)


def flagged_fields(html):
    banner = BANNER.search(html)
    return FLAGGED.findall(banner.group(0)) if banner else []


def named_controls(html):
    return CONTROL.findall(html)


class ARejectedRegistrationKeepsTheSteppedFormTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.c = Client()
        self.fresh = self.c.get('/register/').content.decode()

    def _refused(self, **overrides):
        self.c.post('/register/', a_student())
        return self.c.post('/register/', a_student(**overrides)).content.decode()

    def test_a_duplicate_email_is_refused(self):
        html = self._refused()
        self.assertIn('Email already registered', html)
        self.assertEqual(User.objects.filter(email='juan@bipsu.edu.ph').count(), 1)

    def test_the_refused_form_is_driven_by_the_same_stepper(self):
        html = self._refused()
        self.assertIn('data-steps', form_tag(html))
        self.assertIn('data-steps', form_tag(self.fresh))

    def test_the_refused_form_offers_the_same_sections(self):
        html = self._refused()
        self.assertEqual(STEP_LABEL.findall(html), STEP_LABEL.findall(self.fresh))

    def test_a_duplicate_email_points_at_the_email_box(self):
        html = self._refused(student_id='2022-01000')
        self.assertEqual(flagged_fields(html), ['email'])
        self.assertEqual(named_controls(html).count('email'), 1)

    def test_a_duplicate_student_number_points_at_the_student_number_box(self):
        html = self._refused(email='someone.else@gmail.com')
        self.assertEqual(flagged_fields(html), ['student_id'])
        self.assertEqual(named_controls(html).count('student_id'), 1)

    def test_every_flagged_field_names_a_control_the_form_carries(self):
        html = self.c.post('/register/', {'account_type': 'student'}).content.decode()
        controls = set(named_controls(html))
        flagged = flagged_fields(html)
        self.assertTrue(flagged)
        self.assertEqual(sorted(set(flagged) - controls), [])

    def test_a_staff_registration_flags_its_own_fields_too(self):
        html = self.c.post('/register/', a_staff_member(position='')).content.decode()
        self.assertEqual(flagged_fields(html), ['position'])
        self.assertIn('Position is required', html)

    def test_a_complaint_the_form_cannot_point_at_stays_in_the_banner(self):
        html = self.c.post('/register/', a_student(
            accept_terms='', terms_version='0.0-not-the-current-one')).content.decode()
        self.assertEqual(flagged_fields(html), ['accept_terms', 'accept_terms'])
        self.assertIn('accept_terms', named_controls(html))
