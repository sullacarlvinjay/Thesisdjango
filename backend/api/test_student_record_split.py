from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    AcademicRenewal, AffirmativeStaffApplication, EnrollmentData,
    FamilyBackground, PersonalInformation, Scholarship, ScholarshipLinkRequest,
    StaffProfile, StaffRenewal, StudentProfile, SystemSettings, User,
)
from api.test_registration_payload import a_staff_member


def a_document(name='proof.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


class StudentFactoryMixin:
    def make_student(self, email='ana@bipsu.edu.ph', student_id='2022-00111', **fields):
        user = User.objects.create_user(
            username=email, email=email, password='pw',
            first_name='Ana', last_name='Lim', role='student',
        )
        return StudentProfile.objects.create(user=user, student_id=student_id, **fields)


class MovedColumnsStillReadOffTheProfileTest(StudentFactoryMixin, TestCase):
    def test_create_routes_a_moved_column_to_its_detail_row(self):
        profile = self.make_student(course='BSCS', year_level=3, gwa=1.25,
                                    shs_gpa=91.0, father_last_name='Lim')
        self.assertEqual(profile.enrollment.course, 'BSCS')
        self.assertEqual(profile.enrollment.gwa, 1.25)
        self.assertEqual(profile.affirmative_eligibility.shs_gpa, 91.0)
        self.assertEqual(profile.family.father_last_name, 'Lim')

    def test_reading_a_moved_column_off_the_profile_gives_the_same_value(self):
        self.make_student(course='BSCS', year_level=3, gwa=1.25)
        profile = StudentProfile.objects.get(student_id='2022-00111')
        self.assertEqual(profile.course, 'BSCS')
        self.assertEqual(profile.year_level, 3)
        self.assertEqual(profile.gwa, 1.25)

    def test_assigning_and_saving_writes_through_to_the_detail_row(self):
        profile = self.make_student()
        profile.course = 'BSN'
        profile.family_income = 120000.0
        profile.citizenship = 'Filipino'
        profile.save()

        profile = StudentProfile.objects.get(student_id='2022-00111')
        self.assertEqual(profile.course, 'BSN')
        self.assertEqual(profile.socioeconomic.family_income, 120000.0)
        self.assertEqual(profile.tes_eligibility.citizenship, 'Filipino')

    def test_update_fields_naming_a_moved_column_still_saves_it(self):
        profile = self.make_student(gwa=2.0)
        profile.gwa = 1.4
        profile.save(update_fields=['gwa'])

        profile.refresh_from_db()
        self.assertEqual(profile.gwa, 1.4)

    def test_update_fields_mixing_a_moved_column_with_one_of_its_own(self):
        profile = self.make_student(gwa=2.0)
        profile.gwa = 1.4
        profile.barangay = 'Brgy. Larrazabal'
        profile.save(update_fields=['gwa', 'barangay'])

        profile.refresh_from_db()
        self.assertEqual(profile.gwa, 1.4)
        self.assertEqual(profile.barangay, 'Brgy. Larrazabal')

    def test_refresh_from_db_drops_the_cached_detail_rows(self):
        profile = self.make_student(course='BSCS')
        EnrollmentData.objects.filter(student=profile).update(course='BSN')
        self.assertEqual(profile.course, 'BSCS', 'the cached row should still be in hand')

        profile.refresh_from_db()
        self.assertEqual(profile.course, 'BSN')

    def test_a_new_profile_gets_every_detail_row_even_the_empty_ones(self):
        profile = self.make_student()
        for related in StudentProfile.DETAIL_RELATIONS:
            self.assertIsNotNone(profile.detail(related),
                                 f'{related} row was never written')

    def test_deleting_the_profile_takes_the_detail_rows_with_it(self):
        profile = self.make_student(course='BSCS', father_last_name='Lim')
        profile.delete()
        self.assertEqual(EnrollmentData.objects.count(), 0)
        self.assertEqual(PersonalInformation.objects.count(), 0)
        self.assertEqual(FamilyBackground.objects.count(), 0)

    def test_the_derived_values_still_read_across_the_rows_they_span(self):
        profile = self.make_student(
            middle_name='Reyes', suffix='Jr.',
            suc_exam_score=35.0, suc_exam_total=50.0,
            father_last_name='Lim', father_first_name='Juan',
            father_middle_name='Reyes')
        self.assertEqual(profile.middle_initial, 'R.')
        self.assertEqual(profile.full_name, 'Lim Jr., Ana R.')
        self.assertEqual(profile.suc_exam_percent, 70.0)
        self.assertEqual(profile.suc_exam_display, '35 / 50 (70%)')
        self.assertEqual(profile.father_name, 'Juan R. Lim')

    def test_a_profile_with_no_row_yet_reads_the_default_not_an_error(self):
        profile = self.make_student()
        FamilyBackground.objects.filter(student=profile).delete()
        profile.refresh_from_db()
        self.assertEqual(profile.father_last_name, '')
        self.assertIsNone(profile.household_size)


class EnrollmentDataTest(StudentFactoryMixin, TestCase):
    def test_the_enrollment_columns_round_trip(self):
        profile = self.make_student(
            level='Undergraduate', department='Computer Science Department',
            curriculum='2018-2019', learner_ref_no='123456789012',
            entry_period='1st Semester', entry_date='2022-08-15', exam_score=82.5)
        profile.refresh_from_db()
        self.assertEqual(profile.level, 'Undergraduate')
        self.assertEqual(profile.department, 'Computer Science Department')
        self.assertEqual(profile.curriculum, '2018-2019')
        self.assertEqual(profile.learner_ref_no, '123456789012')
        self.assertEqual(profile.entry_period, '1st Semester')
        self.assertEqual(str(profile.entry_date), '2022-08-15')
        self.assertEqual(profile.exam_score, 82.5)

    def test_the_office_form_offers_the_enrollment_fields_it_saves(self):
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        c = Client()
        self.assertTrue(c.login(email='v@bipsu.edu.ph', password='pw'))
        html = c.get('/vpsea/students/add/').content.decode()
        for field in ('level', 'department', 'curriculum', 'learner_ref_no',
                      'entry_period', 'entry_date', 'exam_score', 'birth_place'):
            self.assertIn(f'name="{field}"', html, f'{field} is not on the form')


class SubmissionsCarryTheirTermTest(StudentFactoryMixin, TestCase):
    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        self.profile = self.make_student()

    def test_registering_records_the_term_the_account_was_made_in(self):
        self.assertEqual(self.profile.term_label, '26-1')
        self.assertEqual(self.profile.school_year, '2026-2027')
        self.assertEqual(self.profile.semester, '1st Semester')

    def test_a_renewal_records_the_semester_it_renews(self):
        renewal = AcademicRenewal.objects.create(
            student=self.profile,
            certificate_of_grades=a_document('cog.pdf'),
            certificate_of_enrollment=a_document('coe.pdf'))
        self.assertEqual(renewal.term_label, '26-1')
        self.assertEqual(renewal.term_display, '2026-2027 1st Semester')

    def test_a_link_request_records_the_term_the_award_is_for(self):
        req = ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='DOST',
            proof_document=a_document())
        self.assertEqual(req.term_label, '26-1')
        self.assertEqual(req.school_year, '2026-2027')

    def test_a_staff_renewal_records_its_term(self):
        staff = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            first_name='Staff', last_name='Member', role='nsu_staff')
        renewal = StaffRenewal.objects.create(staff_user=staff)
        self.assertEqual(renewal.term_label, '26-1')

    def test_a_staff_application_records_its_term(self):
        app = AffirmativeStaffApplication.objects.create(
            full_name='Staff Member', contact_number='09181234567',
            date_of_birth='1990-01-01', course='BSCS')
        self.assertEqual(app.term_label, '26-1')

    def test_the_term_follows_the_active_one_when_it_moves_on(self):
        SystemSettings.objects.filter(pk=1).update(academic_year='26-2')
        renewal = AcademicRenewal.objects.create(
            student=self.profile,
            certificate_of_grades=a_document('cog.pdf'),
            certificate_of_enrollment=a_document('coe.pdf'))
        self.assertEqual(renewal.term_label, '26-2')
        self.assertEqual(renewal.semester, '2nd Semester')

    def test_a_caller_that_knows_the_expanded_term_gets_the_short_key_derived(self):
        req = ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='DOST',
            proof_document=a_document(),
            school_year='2025-2026', semester='2nd Semester')
        self.assertEqual(req.term_label, '25-2')

    def test_a_caller_that_knows_the_short_key_gets_the_expanded_term_derived(self):
        req = ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='CHED', award_tier='Full',
            proof_document=a_document(), term_label='25-1')
        self.assertEqual(req.school_year, '2025-2026')
        self.assertEqual(req.semester, '1st Semester')

    def test_an_award_is_stamped_the_same_way_it_always_was(self):
        scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        from api.models import Application
        award = Application.objects.create(
            student=self.profile, scholarship=scholarship, status='Approved')
        self.assertEqual(award.term_label, '26-1')
        self.assertEqual(award.school_year, '2026-2027')
        self.assertEqual(award.semester, '1st Semester')


class StaffRegistrationPicksASchoolTest(TestCase):
    def setUp(self):
        self.c = Client()

    def _register(self, **overrides):
        data = a_staff_member(
            first_name='Rosa', last_name='Mendoza', email='rosa@bipsu.edu.ph',
            password='demo1234', confirm_password='demo1234',
            school_id='32-1-213313', staff_school='School of Engineering',
            department='Civil Engineering Department', position='Instructor I')
        data.update(overrides)
        return self.c.post('/register/', data)

    def test_the_form_asks_staff_to_type_it(self):
        html = self.c.get('/register/').content.decode()
        self.assertIn('<label>Office / College / Unit</label>', html)
        self.assertIn('name="staff_school"', html)
        self.assertNotIn('list="bipsuStaffUnits"', html)
        self.assertNotIn('<datalist id="bipsuStaffUnits">', html)

    def test_a_unit_that_is_not_on_the_list_still_reaches_the_profile(self):
        self._register(staff_school='Office of Digital Transformation')
        staff = StaffProfile.objects.get(user__email='rosa@bipsu.edu.ph')
        self.assertEqual(staff.school, 'Office of Digital Transformation')

    def test_the_school_picked_at_signup_reaches_the_staff_profile(self):
        self._register()
        staff = StaffProfile.objects.get(user__email='rosa@bipsu.edu.ph')
        self.assertEqual(staff.school, 'School of Engineering')
        self.assertEqual(staff.department, 'Civil Engineering Department')

    def test_registering_does_not_pre_create_an_application(self):
        self._register()
        self.assertFalse(
            AffirmativeStaffApplication.objects.filter(email='rosa@bipsu.edu.ph').exists(),
            'registering is not applying')

    def test_a_rejected_signup_comes_back_with_the_unit_still_filled_in(self):
        r = self._register(confirm_password='different')
        self.assertContains(r, 'Passwords do not match')
        self.assertContains(r, 'name="staff_school" value="School of Engineering"')

    def test_the_students_own_school_field_is_not_what_staff_posts(self):
        self._register(school='School of Nursing and Health Sciences')
        staff = StaffProfile.objects.get(user__email='rosa@bipsu.edu.ph')
        self.assertEqual(staff.school, 'School of Engineering')


class TheRestApiKeepsItsShapeTest(StudentFactoryMixin, TestCase):
    def setUp(self):
        from rest_framework.authtoken.models import Token
        self.profile = self.make_student(course='BSCS', year_level=3, gwa=1.25,
                                         family_income=120000.0)
        token, _ = Token.objects.get_or_create(user=self.profile.user)
        self.c = Client(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_the_profile_endpoint_still_returns_the_moved_columns(self):
        body = self.c.get('/api/student/profile/').json()
        self.assertEqual(body['course'], 'BSCS')
        self.assertEqual(body['gwa'], 1.25)
        self.assertEqual(body['family_income'], 120000.0)
        for key in ('shs_gpa', 'citizenship', 'father_last_name', 'elementary',
                    'birth_place', 'learner_ref_no'):
            self.assertIn(key, body, f'{key} dropped out of the response')

    def test_patching_a_moved_column_through_the_api_persists_it(self):
        r = self.c.patch('/api/student/profile/',
                         {'gwa': 1.10, 'shs_gpa': 91.5, 'father_last_name': 'Lim'},
                         content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.gwa, 1.10)
        self.assertEqual(self.profile.shs_gpa, 91.5)
        self.assertEqual(self.profile.father_last_name, 'Lim')

    def test_the_analytics_endpoint_still_bands_students_by_gwa(self):
        from rest_framework.authtoken.models import Token
        officer = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        token, _ = Token.objects.get_or_create(user=officer)
        c = Client(HTTP_AUTHORIZATION=f'Token {token.key}')
        body = c.get('/api/vpsea/analytics/').json()
        bands = {row['range']: row['count'] for row in body['gpa_distribution']}
        self.assertEqual(bands['1.00-1.25'], 1, 'the 1.25 student was not counted')
        self.assertEqual(bands['1.26-1.50'], 0)

    def test_the_analytics_endpoint_still_groups_scholars_by_course(self):
        from rest_framework.authtoken.models import Token
        scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        from api.models import Application
        Application.objects.create(student=self.profile, scholarship=scholarship,
                                   status='Approved')
        officer = User.objects.create_user(
            username='v2@bipsu.edu.ph', email='v2@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        token, _ = Token.objects.get_or_create(user=officer)
        c = Client(HTTP_AUTHORIZATION=f'Token {token.key}')
        body = c.get('/api/vpsea/analytics/').json()
        self.assertEqual(body['course_distribution'],
                         [{'course': 'BSCS', 'scholars': 1}])


class TheCancelButtonStaysOnThisSiteTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def cancel_url(self, **params):
        return self.c.get('/vpsea/students/add/', params).context['cancel_url']

    def test_a_path_on_this_site_is_kept(self):
        self.assertEqual(
            self.cancel_url(next='/vpsea/archives/?type=CHED'),
            '/vpsea/archives/?type=CHED')

    def test_no_parameter_falls_back_to_the_student_list(self):
        self.assertEqual(self.cancel_url(), '/vpsea/students/')

    def test_another_site_is_refused(self):
        for elsewhere in ('https://evil.example/phish',
                          '//evil.example/phish',
                          'http://evil.example',
                          'javascript:alert(1)'):
            with self.subTest(next=elsewhere):
                self.assertEqual(self.cancel_url(next=elsewhere),
                                 '/vpsea/students/',
                                 f'{elsewhere} reached the Cancel button')

    def test_the_edit_form_is_held_to_the_same_rule(self):
        user = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Cruz', role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id='2026-0001', course='BSCS')
        page = self.c.get(f'/vpsea/students/{profile.pk}/edit/',
                          {'next': 'https://evil.example/phish'})
        self.assertEqual(page.context['cancel_url'], '/vpsea/students/')
