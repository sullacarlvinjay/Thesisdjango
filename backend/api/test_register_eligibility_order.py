import re

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import SystemSettings
from api.fixtures_registration import a_declared_scholar, a_student


def _card(html, element_id):
    match = re.search(r'<div[^>]*id="' + element_id + r'"[^>]*>', html)
    return match.group(0) if match else ''


class RegisterEligibilityOrderTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.c = Client()

    def _form(self, **post):
        if post:
            return self.c.post('/register/', a_student(
                email='juan@gmail.com', student_id='23-0001',
                password='pw12345', confirm_password='different',
                **post)).content.decode()
        return self.c.get('/register/').content.decode()

    def test_both_eligibility_cards_come_after_scholarship_data(self):
        html = self._form()
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertLess(html.index('id="scholarshipData"'),
                                html.index(f'id="{card}"'),
                                f'{card} still renders before Scholarship Data')

    def test_scholarship_eligibility_comes_before_tes_eligibility(self):
        html = self._form()
        self.assertLess(html.index('id="scholarshipEligibility"'),
                        html.index('id="tesEligibility"'))

    def test_they_stay_inside_the_form(self):
        html = self._form()
        self.assertLess(html.index('id="tesEligibility"'), html.index('</form>'))

    def test_a_blank_form_asks_both(self):
        html = self._form()
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertNotIn('hidden', _card(html, card))

    def test_declaring_a_scholarship_hides_both(self):
        html = self._form(has_scholarship='on', scholarship_type='DOST')
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertIn('hidden', _card(html, card),
                              f'{card} was still asked of a declared scholar')

    def test_the_scholarship_data_card_opens_in_their_place(self):
        html = self._form(has_scholarship='on', scholarship_type='DOST')
        self.assertNotIn('hidden', _card(html, 'scholarshipData'))

    def test_not_declaring_leaves_them_asked(self):
        html = self._form()
        self.assertIn('hidden', _card(html, 'scholarshipData'))
        self.assertNotIn('hidden', _card(html, 'scholarshipEligibility'))

    def test_a_staff_form_hides_them_whatever_the_box_says(self):
        html = self._form(account_type='nsu_staff')
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertIn('hidden', _card(html, card))

    def test_a_student_who_holds_nothing_is_asked_all_of_it(self):
        from api.models import User

        data = a_student(email='ana@gmail.com', student_id='23-0002')
        for question in ('citizenship', 'is_4ps_beneficiary'):
            del data[question]
        r = self.c.post('/register/', data)
        self.assertContains(r, 'Citizenship is required')
        self.assertContains(r, 'please answer Yes or No')
        self.assertFalse(User.objects.filter(email='ana@gmail.com').exists())

    def test_a_student_cannot_register_without_an_shs_gpa(self):
        from api.models import User

        data = a_student(email='cora@gmail.com', student_id='23-0004')
        del data['shs_gpa']
        r = self.c.post('/register/', data)
        self.assertContains(r, 'SHS Grade Point Average is required')
        self.assertFalse(User.objects.filter(email='cora@gmail.com').exists())

    def test_every_eligibility_answer_is_asked_for_by_name(self):
        from api.models import User

        data = a_student(email='dina@gmail.com', student_id='23-0005')
        for question in ('shs_gpa', 'suc_exam_score', 'suc_exam_total'):
            del data[question]
        r = self.c.post('/register/', data)
        for wanted in ('SHS Grade Point Average is required',
                       'SUC Admission Exam Score is required',
                       'SUC Admission Exam Score — total items is required'):
            with self.subTest(error=wanted):
                self.assertContains(r, wanted)
        self.assertFalse(User.objects.filter(email='dina@gmail.com').exists())

    def test_a_student_cannot_register_without_the_certificates(self):
        from api.models import User

        data = a_student(email='elsa@gmail.com', student_id='23-0006')
        for upload in ('shs_gpa_cert', 'suc_exam_cert'):
            del data[upload]
        r = self.c.post('/register/', data)
        self.assertContains(r, 'SHS GPA Certificate is required')
        self.assertContains(r, 'SUC Exam Certificate is required')
        self.assertFalse(User.objects.filter(email='elsa@gmail.com').exists())

    def test_a_complete_eligibility_card_registers(self):
        from api.models import User

        data = a_student(email='fely@gmail.com', student_id='23-0007')
        self.assertEqual(self.c.post('/register/', data).status_code, 302)
        user = User.objects.filter(email='fely@gmail.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.profile.shs_gpa, 92.5)
        self.assertTrue(user.profile.shs_gpa_cert)
        self.assertTrue(user.profile.suc_exam_cert)

    def test_the_form_makes_the_browser_ask_for_every_eligibility_answer(self):
        html = self._form()
        for name in ('shs_gpa', 'shs_gpa_cert',
                     'suc_exam_score', 'suc_exam_total', 'suc_exam_cert'):
            with self.subTest(field=name):
                field = re.search(rf'<input[^>]*name="{name}"[^>]*>',
                                  html).group(0)
                self.assertRegex(field, r'\brequired\b')

    def test_a_declared_scholar_is_still_asked_for_none_of_it(self):
        from api.models import User

        data = a_declared_scholar(email='gina@gmail.com', student_id='23-0008',
                                  scholarship_type='DOST')
        data['proof_document'] = SimpleUploadedFile(
            'award.pdf', b'%PDF-1.4 award letter', content_type='application/pdf')
        self.assertEqual(self.c.post('/register/', data).status_code, 302)
        self.assertTrue(User.objects.filter(email='gina@gmail.com').exists())

    def test_a_declared_scholar_registers_with_the_cards_posting_nothing(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from api.models import ScholarshipLinkRequest, User

        self.c.post('/register/', a_declared_scholar(
            email='ben@gmail.com', student_id='23-0003',
            scholarship_type='DOST',
            proof_document=SimpleUploadedFile(
                'award.pdf', b'%PDF-1.4 award letter', content_type='application/pdf'),
        ))
        self.assertTrue(User.objects.filter(email='ben@gmail.com').exists())
        self.assertTrue(ScholarshipLinkRequest.objects.filter(
            student__user__email='ben@gmail.com', scholarship_type='DOST').exists())

    def test_both_cards_are_still_marked_student_only(self):
        html = self._form()
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertIn('data-student-only', _card(html, card))
