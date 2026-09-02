"""The student record split across detail rows, and the term on every submission.

StudentProfile had grown to forty columns covering six unrelated subjects. They
moved onto :class:`~api.models.StudentDetail` rows keyed back to the profile,
and the profile proxies them so nothing that reads a student had to move too —
these tests are what says that stayed true.

The second half covers the other half of the change: a submission used to say
only when it arrived, and the office had to infer the semester it belonged to
from that date. Registration, applications, renewals, link requests and TES
applications now carry the term as a column.
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    AcademicRenewal, AffirmativeStaffApplication, EnrollmentData,
    FamilyBackground, PersonalInformation, Scholarship, ScholarshipLinkRequest,
    StaffProfile, StaffRenewal, StudentProfile, SystemSettings, TESApplication,
    User,
)


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
    """The whole point of the split: no caller had to learn where a field went."""

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
        """Callers were passing update_fields=['gwa'] before the split and still are."""
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
        """A detail row is made on demand, so a read before one exists still answers."""
        profile = self.make_student()
        FamilyBackground.objects.filter(student=profile).delete()
        profile.refresh_from_db()
        self.assertEqual(profile.father_last_name, '')
        self.assertIsNone(profile.household_size)


class EnrollmentDataTest(StudentFactoryMixin, TestCase):
    """The registrar's own columns, which had no home on the profile before."""

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
        officer = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        c = Client()
        self.assertTrue(c.login(email='v@bipsu.edu.ph', password='pw'))
        html = c.get('/vpsea/students/add/').content.decode()
        for field in ('level', 'department', 'curriculum', 'learner_ref_no',
                      'entry_period', 'entry_date', 'exam_score', 'birth_place'):
            self.assertIn(f'name="{field}"', html, f'{field} is not on the form')


class SubmissionsCarryTheirTermTest(StudentFactoryMixin, TestCase):
    """Every record a person sends says which semester it belongs to."""

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

    def test_a_tes_application_records_the_term_it_was_applied_in(self):
        app = TESApplication.objects.create(student=self.profile, lrn='1')
        self.assertEqual(app.term_label, '26-1')
        self.assertEqual(app.semester, '1st Semester')

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
        app = TESApplication.objects.create(
            student=self.profile, school_year='2025-2026', semester='2nd Semester')
        self.assertEqual(app.term_label, '25-2')

    def test_a_caller_that_knows_the_short_key_gets_the_expanded_term_derived(self):
        req = ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='CHED', award_tier='Full',
            proof_document=a_document(), term_label='25-1')
        self.assertEqual(req.school_year, '2025-2026')
        self.assertEqual(req.semester, '1st Semester')

    def test_an_award_is_stamped_the_same_way_it_always_was(self):
        """Application had these columns first; it reads them off TermStamped now."""
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
    """Staff typed their school free-hand; students never could."""

    def setUp(self):
        self.c = Client()

    def _register(self, **overrides):
        data = {
            'account_type': 'nsu_staff',
            'first_name': 'Rosa', 'last_name': 'Mendoza',
            'email': 'rosa@bipsu.edu.ph',
            'password': 'demo1234', 'confirm_password': 'demo1234',
            'school_id': '32-1-213313', 'staff_school': 'School of Engineering',
            'department': 'Civil Engineering Department', 'position': 'Instructor I',
        }
        data.update(overrides)
        return self.c.post('/register/', data)

    def test_the_form_offers_a_school_dropdown_to_staff(self):
        html = self.c.get('/register/').content.decode()
        self.assertIn('<select name="staff_school"', html)
        self.assertIn('School of Engineering', html)

    def test_the_school_picked_at_signup_reaches_the_staff_profile(self):
        self._register()
        staff = StaffProfile.objects.get(user__email='rosa@bipsu.edu.ph')
        self.assertEqual(staff.school, 'School of Engineering')
        self.assertEqual(staff.department, 'Civil Engineering Department')

    def test_registering_does_not_pre_create_an_application(self):
        """Registration used to open a Draft for the apply page to continue from.

        The Draft status is gone, and with it the half-finished row: an
        application is created when the staff member actually applies. Their
        school is on the StaffProfile, which the apply form reads.
        """
        self._register()
        self.assertFalse(
            AffirmativeStaffApplication.objects.filter(email='rosa@bipsu.edu.ph').exists(),
            'registering is not applying')

    def test_a_rejected_signup_comes_back_with_the_school_still_selected(self):
        r = self._register(confirm_password='different')
        self.assertContains(r, 'Passwords do not match')
        self.assertContains(r, 'value="School of Engineering" selected')

    def test_the_students_own_school_field_is_not_what_staff_posts(self):
        """Both blocks live in one form, and request.POST keeps only the last value."""
        self._register(school='School of Nursing and Health Sciences')
        staff = StaffProfile.objects.get(user__email='rosa@bipsu.edu.ph')
        self.assertEqual(staff.school, 'School of Engineering')


class TheRestApiKeepsItsShapeTest(StudentFactoryMixin, TestCase):
    """The JSON surface predates the split and cannot be allowed to notice it.

    Both of these broke when the columns moved and nothing caught it: the
    profile endpoint returns `fields = '__all__'`, which stopped seeing forty of
    them, and the analytics endpoint filtered and grouped on `gwa` and `course`
    off the profile table, where they no longer are.
    """

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
