import re

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.constants import academic_classification
from api.models import Application, Scholarship, StudentProfile, User

TYPED = {
    'action': 'submit',
    'course': 'BSCS',
    'elementary': 'Naval Central School',
    'highschool': 'Biliran NHS',
    'last_school': 'Biliran NHS',
    'father_name': 'Jose Lim',
    'father_occupation': 'Farmer',
    'mother_name': 'Rosa Lim',
    'mother_occupation': 'Teacher',
    'semester': '1st Semester',
    'school_year': '2025-2026',
    'gwa': '1.4',
}

DOCUMENTS = ('doc_certificate_of_grades', 'doc_certificate_of_enrollment',
             'doc_prospectus', 'doc_id_photo', 'doc_application_form')


def a_document(name):
    return SimpleUploadedFile(f'{name}.pdf', b'%PDF-1.4 proof',
                              content_type='application/pdf')


def a_complete_application(**overrides):
    data = dict(TYPED, **{name: a_document(name) for name in DOCUMENTS})
    data.update(overrides)
    return data


def a_student_who_can_apply(**profile_fields):
    user = User.objects.create_user(
        username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
        first_name='Ana', last_name='Lim', role='student',
    )
    fields = {
        'student_id': '2022-00111', 'course': 'BSCS', 'year_level': 2,
        'date_of_birth': '2004-03-11', 'gender': 'Female',
        'contact_number': '09171234567',
        'barangay': 'Brgy. Larrazabal', 'municipality': 'Naval',
        'province': 'Biliran',
    }
    fields.update(profile_fields)
    return user, StudentProfile.objects.create(user=user, **fields)


class ApplyingStudentTestCase(TestCase):
    def setUp(self):
        self.user, self.profile = a_student_who_can_apply()
        Scholarship.objects.create(name='Academic Scholarship', type='Academic',
                                   category='Merit-Based')
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def _apply(self, **overrides):
        return self.c.post('/student/apply/academic/',
                           a_complete_application(**overrides))

    def _page(self):
        return self.c.get('/student/apply/academic/').content.decode()


class AcademicClassificationTest(TestCase):
    def test_the_ceilings_match_what_the_page_prints(self):
        self.assertEqual(academic_classification(1.00), 'University Scholar')
        self.assertEqual(academic_classification(1.29), 'University Scholar')
        self.assertEqual(academic_classification(1.30), 'College Scholar')
        self.assertEqual(academic_classification(1.50), 'College Scholar')
        self.assertEqual(academic_classification(1.51), 'Not Eligible')

    def test_an_empty_gwa_is_not_a_perfect_one(self):
        self.assertEqual(academic_classification(0), '')
        self.assertEqual(academic_classification(0.0), '')
        self.assertEqual(academic_classification(None), '')


class DeclaredGWAReachesTheProfileTest(ApplyingStudentTestCase):

    def test_the_profile_starts_at_the_zero_that_caused_this(self):
        self.assertEqual(self.profile.gwa, 0.0)

    def test_applying_saves_the_gwa_the_student_declared(self):
        self._apply(gwa='1.4')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.gwa, 1.4)

    def test_the_panel_then_reads_back_what_was_declared(self):
        self._apply(gwa='1.4')
        self.profile.refresh_from_db()
        self.assertEqual(academic_classification(self.profile.gwa), 'College Scholar')

    def test_a_junk_gwa_never_overwrites_a_real_one(self):
        self.profile.gwa = 1.2
        self.profile.save()
        for junk in ('', 'abc', '0', '9.9', '-1'):
            self._apply(gwa=junk)
            self.profile.refresh_from_db()
            self.assertEqual(self.profile.gwa, 1.2, f'{junk!r} overwrote a real GWA')
            Application.objects.all().delete()

    def test_the_application_still_keeps_its_own_copy_of_the_form(self):
        self._apply(gwa='1.4')
        app = Application.objects.get(student=self.profile)
        self.assertEqual(app.form_data['gwa'], '1.4')


class NothingMayBeMissingWhenApplyingTest(ApplyingStudentTestCase):

    def test_a_complete_application_is_filed(self):
        r = self._apply()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Application.objects.count(), 1)

    def test_a_complete_application_files_all_five_documents(self):
        self._apply()
        app = Application.objects.get(student=self.profile)
        self.assertEqual(app.documents.count(), 5)

    def test_any_blank_answer_stops_the_whole_application(self):
        for name in ('course', 'elementary', 'highschool', 'last_school',
                     'father_name', 'father_occupation', 'mother_name',
                     'mother_occupation', 'semester', 'school_year', 'gwa'):
            with self.subTest(field=name):
                r = self._apply(**{name: ''})
                self.assertEqual(r.status_code, 200)
                self.assertFalse(Application.objects.exists(),
                                 f'a blank {name} was filed anyway')

    def test_each_blank_answer_is_named_on_the_page(self):
        for name, label in (('course', 'Course is required'),
                            ('elementary', 'Elementary School is required'),
                            ('highschool', 'High School is required'),
                            ('last_school', 'Last School Attended is required'),
                            ('father_name', 'Name is required'),
                            ('mother_occupation', 'Occupation is required')):
            with self.subTest(field=name):
                self.assertContains(self._apply(**{name: ''}), label)

    def test_a_missing_document_stops_the_application(self):
        for name in DOCUMENTS:
            with self.subTest(document=name):
                data = a_complete_application()
                del data[name]
                r = self.c.post('/student/apply/academic/', data)
                self.assertEqual(r.status_code, 200)
                self.assertFalse(Application.objects.exists(),
                                 f'a missing {name} was filed anyway')

    def test_the_missing_document_is_named(self):
        data = a_complete_application()
        del data['doc_prospectus']
        self.assertContains(self.c.post('/student/apply/academic/', data),
                            'Prospectus is required')

    def test_everything_missing_at_once_is_listed_at_once(self):
        r = self.c.post('/student/apply/academic/', {'action': 'submit'})
        self.assertContains(r, 'Course is required')
        self.assertContains(r, 'Certificate Of Grades is required')
        self.assertContains(r, 'Enter your GWA before sending')

    def test_a_refusal_saves_no_documents(self):
        from api.models import ApplicationDocument

        self._apply(course='')
        self.assertFalse(ApplicationDocument.objects.exists())

    def test_what_the_student_typed_survives_the_refusal(self):
        r = self._apply(course='', elementary='Caraycaray Elementary')
        self.assertContains(r, 'value="Caraycaray Elementary"')

    def test_every_answer_the_browser_can_check_is_marked_required(self):
        html = self._page()
        for name in ('course', 'elementary', 'highschool', 'last_school',
                     'father_name', 'father_occupation', 'mother_name',
                     'mother_occupation', 'gwa'):
            with self.subTest(field=name):
                field = re.search(rf'<input[^>]*name="{name}"[^>]*>',
                                  html).group(0)
                self.assertRegex(field, r'\brequired\b')

    def test_every_document_is_marked_required(self):
        html = self._page()
        for name in DOCUMENTS:
            with self.subTest(document=name):
                field = re.search(rf'<input[^>]*name="{name}"[^>]*>',
                                  html).group(0)
                self.assertRegex(field, r'\brequired\b')

    def test_an_edit_may_lean_on_the_documents_already_on_file(self):
        self._apply()
        app = Application.objects.get(student=self.profile)
        app.status = 'Needs Revision'
        app.save(update_fields=['status'])

        r = self.c.post('/student/apply/academic/', dict(TYPED, gwa='1.25'))
        self.assertEqual(r.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.status, 'Pending Validation')
        self.assertEqual(app.form_data['gwa'], '1.25')

    def test_an_edit_still_may_not_blank_an_answer(self):
        self._apply()
        app = Application.objects.get(student=self.profile)
        app.status = 'Needs Revision'
        app.remarks = 'Fix this'
        app.save(update_fields=['status', 'remarks'])

        r = self.c.post('/student/apply/academic/', dict(TYPED, course=''))
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'Needs Revision')
        self.assertEqual(app.remarks, 'Fix this')


class ARecordWithHolesCannotApplyTest(TestCase):
    def setUp(self):
        Scholarship.objects.create(name='Academic Scholarship', type='Academic',
                                   category='Merit-Based')
        self.c = Client()

    def _apply_as(self, **profile_fields):
        _user, self.profile = a_student_who_can_apply(**profile_fields)
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))
        return self.c.post('/student/apply/academic/', a_complete_application())

    def test_a_record_with_no_birth_date_is_sent_to_my_profile(self):
        r = self._apply_as(date_of_birth=None)
        self.assertContains(r, 'Birth Date')
        self.assertContains(r, 'My Profile')
        self.assertFalse(Application.objects.exists())

    def test_a_record_with_no_contact_number_is_refused(self):
        r = self._apply_as(contact_number='')
        self.assertContains(r, 'Contact Number')
        self.assertFalse(Application.objects.exists())

    def test_a_record_with_no_address_is_refused(self):
        r = self._apply_as(barangay='', municipality='', province='')
        self.assertContains(r, 'Address')
        self.assertFalse(Application.objects.exists())

    def test_a_record_with_no_gender_is_refused(self):
        r = self._apply_as(gender='')
        self.assertContains(r, 'Gender')
        self.assertFalse(Application.objects.exists())

    def test_a_complete_record_is_let_through(self):
        r = self._apply_as()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Application.objects.count(), 1)


class DraftingIsGoneTest(ApplyingStudentTestCase):

    def test_the_page_no_longer_offers_a_draft_button(self):
        html = self._page()
        self.assertNotIn('value="draft"', html)
        self.assertIn('value="submit"', html)

    def test_the_form_opts_into_the_browser_side_cache(self):
        html = self._page()
        self.assertIn('data-cache="apply-academic"', html)
        self.assertRegex(html, r'form-cache(\.[0-9a-f]+)?\.js')

    def test_a_posted_draft_action_is_submitted_anyway_not_parked(self):
        self._apply(action='draft')
        app = Application.objects.get(student=self.profile)
        self.assertEqual(app.status, 'Pending Validation')

    def test_the_blocked_page_does_not_ship_a_broken_script(self):
        Application.objects.create(
            student=self.profile, scholarship=Scholarship.objects.first(),
            status='Approved', form_data={})
        html = self._page()
        self.assertNotIn('MAX = ;', html)
        self.assertNotIn('UNIVERSITY_MAX', html)
