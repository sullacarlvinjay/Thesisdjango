from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    ApplicantRecord, ApplicantAffirmativeEligibility,
    ApplicantEmployment, ApplicantEnrollment, ApplicantInformation,
    ApplicantStaffEligibility, StaffEducation, StaffEmployment,
    StaffPersonalInformation, StaffProfile, StudentProfile, SystemSettings, User,
)


def a_document(name='appointment.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


class StaffFactoryMixin:
    def make_staff(self, email='maria@bipsu.edu.ph', employee_id='32-1-213313', **fields):
        user = User.objects.create_user(
            username=email, email=email, password='pw',
            first_name='Maria', last_name='Santos', role='nsu_staff',
        )
        return StaffProfile.objects.create(user=user, employee_id=employee_id, **fields)

    def make_application(self, **fields):
        fields.setdefault('full_name', 'Maria Santos')
        fields.setdefault('email', 'maria@bipsu.edu.ph')
        fields.setdefault('qualified_for', 'Staff')
        return ApplicantRecord.objects.create(**fields)


class StaffProfileColumnsStillReadOffTheProfileTest(StaffFactoryMixin, TestCase):
    def test_create_routes_a_moved_column_to_its_detail_row(self):
        staff = self.make_staff(position='Instructor I', employment_status='Regular',
                                middle_name='Reyes', highest_education='MA Education')
        self.assertEqual(staff.employment.position, 'Instructor I')
        self.assertEqual(staff.employment.employment_status, 'Regular')
        self.assertEqual(staff.personal.middle_name, 'Reyes')
        self.assertEqual(staff.education.highest_education, 'MA Education')

    def test_reading_a_moved_column_off_the_profile_gives_the_same_value(self):
        self.make_staff(position='Instructor I', department='Teacher Education')
        staff = StaffProfile.objects.get(employee_id='32-1-213313')
        self.assertEqual(staff.position, 'Instructor I')
        self.assertEqual(staff.department, 'Teacher Education')

    def test_assigning_and_saving_writes_through_to_the_detail_row(self):
        staff = self.make_staff()
        staff.position = 'Associate Professor I'
        staff.civil_status = 'Married'
        staff.has_baccalaureate = True
        staff.save()

        staff = StaffProfile.objects.get(employee_id='32-1-213313')
        self.assertEqual(staff.employment.position, 'Associate Professor I')
        self.assertEqual(staff.personal.civil_status, 'Married')
        self.assertTrue(staff.education.has_baccalaureate)

    def test_update_fields_naming_a_moved_column_still_saves_it(self):
        staff = self.make_staff(position='Instructor I')
        staff.position = 'Instructor II'
        staff.save(update_fields=['position'])

        staff = StaffProfile.objects.get(employee_id='32-1-213313')
        self.assertEqual(staff.position, 'Instructor II')

    def test_update_fields_mixing_a_moved_column_with_one_of_its_own(self):
        staff = self.make_staff()
        staff.employee_id = '32-1-999999'
        staff.school = 'College of Education'
        staff.save(update_fields=['employee_id', 'school'])

        staff = StaffProfile.objects.get(pk=staff.pk)
        self.assertEqual(staff.employee_id, '32-1-999999')
        self.assertEqual(staff.school, 'College of Education')

    def test_refresh_from_db_drops_the_cached_detail_rows(self):
        staff = self.make_staff(position='Instructor I')
        StaffEmployment.objects.filter(staff=staff).update(position='Dean')
        staff.refresh_from_db()
        self.assertEqual(staff.position, 'Dean')

    def test_a_new_profile_gets_every_detail_row_even_the_empty_ones(self):
        staff = self.make_staff()
        self.assertTrue(StaffEmployment.objects.filter(staff=staff).exists())
        self.assertTrue(StaffPersonalInformation.objects.filter(staff=staff).exists())
        self.assertTrue(StaffEducation.objects.filter(staff=staff).exists())

    def test_deleting_the_profile_takes_the_detail_rows_with_it(self):
        staff = self.make_staff()
        staff.delete()
        self.assertEqual(StaffEmployment.objects.count(), 0)
        self.assertEqual(StaffPersonalInformation.objects.count(), 0)
        self.assertEqual(StaffEducation.objects.count(), 0)

    def test_a_profile_with_no_row_yet_reads_the_default_not_an_error(self):
        staff = self.make_staff()
        StaffEducation.objects.filter(staff=staff).delete()
        staff.refresh_from_db()
        self.assertEqual(staff.highest_education, '')
        self.assertFalse(staff.has_baccalaureate)


class StaffProfileDerivedValuesTest(StaffFactoryMixin, TestCase):
    def test_years_of_service_still_counts_from_the_hiring_date(self):
        staff = self.make_staff(date_hired=date(2016, 6, 1))
        expected = date.today().year - 2016 - (
            (date.today().month, date.today().day) < (6, 1))
        self.assertEqual(staff.years_of_service, expected)

    def test_years_of_service_falls_back_to_the_declared_count(self):
        staff = self.make_staff(declared_years_of_service=12)
        self.assertEqual(staff.years_of_service, 12)

    def test_is_regular_still_reads_the_employment_status(self):
        self.assertTrue(self.make_staff(employment_status='Regular').is_regular)

    def test_is_regular_is_false_for_any_other_appointment(self):
        staff = self.make_staff(employee_id='32-1-000002', employment_status='Contractual')
        self.assertFalse(staff.is_regular)

    def test_full_name_still_spans_the_user_row_and_the_personal_row(self):
        staff = self.make_staff(middle_name='Reyes', suffix='Jr.')
        self.assertEqual(staff.full_name, 'Santos Jr., Maria R.')

    def test_middle_initial_is_still_derived_from_the_moved_middle_name(self):
        self.assertEqual(self.make_staff(middle_name='Reyes').middle_initial, 'R.')


class StaffScholarEnrolmentTest(StaffFactoryMixin, TestCase):
    def test_the_course_a_staff_scholar_is_taking_lands_on_the_education_row(self):
        staff = self.make_staff(course='MA Education', year_level=2)
        self.assertEqual(staff.education.course, 'MA Education')
        self.assertEqual(staff.education.year_level, 2)

    def test_it_reads_back_off_the_profile_like_every_other_moved_column(self):
        self.make_staff(course='MA Education', year_level=2)
        staff = StaffProfile.objects.get(employee_id='32-1-213313')
        self.assertEqual(staff.course, 'MA Education')
        self.assertEqual(staff.year_level, 2)

    def test_the_year_level_defaults_to_one_like_the_student_record(self):
        self.assertEqual(self.make_staff().year_level, 1)

    def test_what_they_study_is_not_where_they_work(self):
        staff = self.make_staff(course='MA Education', department='Teacher Education',
                                position='Instructor I')
        self.assertEqual(staff.education.course, 'MA Education')
        self.assertEqual(staff.employment.department, 'Teacher Education')
        self.assertEqual(staff.employment.position, 'Instructor I')

    def test_a_queryset_reaches_it_through_the_education_relation(self):
        self.make_staff(course='MA Education')
        rows = StaffProfile.objects.filter(
            education__course='MA Education').values_list('employee_id', flat=True)
        self.assertEqual(list(rows), ['32-1-213313'])


class ApplicationColumnsStillReadOffTheApplicationTest(StaffFactoryMixin, TestCase):
    def test_create_routes_every_group_to_its_detail_row(self):
        app = self.make_application(
            course='MA Education', year_level=1, gender='Female',
            is_nsu_staff=True, employment_status='Regular', shs_gpa=91.5)
        self.assertEqual(app.enrollment.course, 'MA Education')
        self.assertEqual(app.applicant.gender, 'Female')
        self.assertTrue(app.staff_eligibility.is_nsu_staff)
        self.assertEqual(app.employment.employment_status, 'Regular')
        self.assertEqual(app.affirmative_eligibility.shs_gpa, 91.5)

    def test_reading_a_moved_column_off_the_application_gives_the_same_value(self):
        self.make_application(course='BS Biology', student_id='2022-00111')
        app = ApplicantRecord.objects.get(email='maria@bipsu.edu.ph')
        self.assertEqual(app.course, 'BS Biology')
        self.assertEqual(app.student_id, '2022-00111')

    def test_assigning_and_saving_writes_through(self):
        app = self.make_application()
        app.designation = 'Faculty'
        app.suc_exam_score = 42.0
        app.save()

        app = ApplicantRecord.objects.get(pk=app.pk)
        self.assertEqual(app.employment.designation, 'Faculty')
        self.assertEqual(app.affirmative_eligibility.suc_exam_score, 42.0)

    def test_a_new_application_gets_every_detail_row(self):
        app = self.make_application()
        for model in (ApplicantInformation, ApplicantEnrollment,
                      ApplicantStaffEligibility, ApplicantEmployment,
                      ApplicantAffirmativeEligibility):
            self.assertTrue(model.objects.filter(application=app).exists(), model.__name__)

    def test_deleting_the_application_takes_the_detail_rows_with_it(self):
        self.make_application().delete()
        self.assertEqual(ApplicantEnrollment.objects.count(), 0)
        self.assertEqual(ApplicantAffirmativeEligibility.objects.count(), 0)

    def test_the_term_stamp_still_fills_itself_in(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        app = self.make_application()
        self.assertEqual(app.term_label, '26-1')
        self.assertEqual(app.school_year, '2026-2027')

    def test_the_derived_values_still_read_across_the_rows_they_span(self):
        app = self.make_application(suc_exam_score=42.0, suc_exam_total=50.0)
        self.assertEqual(app.suc_exam_percent, 84.0)
        self.assertIn('42', app.suc_exam_display)

    def test_is_regular_staff_still_decides_the_one_eligibility_rule(self):
        staff_row = self.make_application(is_nsu_staff=True, employment_status='Regular')
        self.assertTrue(staff_row.is_regular_staff)

    def test_is_regular_staff_refuses_a_non_regular_appointment(self):
        app = self.make_application(is_nsu_staff=True, employment_status='Contractual')
        self.assertFalse(app.is_regular_staff)

    def test_a_dependent_qualifies_on_the_sponsoring_employee_id(self):
        app = self.make_application(is_nsu_dependent=True, staff_employee_id='EMP-0042')
        self.assertTrue(app.is_regular_staff)

    def test_a_dependent_with_no_sponsor_does_not_qualify(self):
        app = self.make_application(is_nsu_dependent=True, staff_employee_id='')
        self.assertFalse(app.is_regular_staff)

    def test_name_parts_still_split_the_unmoved_full_name(self):
        app = self.make_application(full_name='Juan Reyes Santos')
        self.assertEqual((app.last_name, app.first_name, app.middle_name),
                         ('Santos', 'Juan', 'Reyes'))


class OneTableTwoProgrammesTest(StaffFactoryMixin, TestCase):
    def test_a_staff_row_leaves_the_affirmative_group_empty(self):
        app = self.make_application(
            qualified_for='Staff', is_nsu_staff=True,
            employment_status='Regular', position='Instructor I')
        self.assertEqual(app.employment.position, 'Instructor I')
        self.assertIsNone(app.affirmative_eligibility.shs_gpa)
        self.assertIsNone(app.affirmative_eligibility.suc_exam_score)

    def test_an_affirmative_row_leaves_the_employment_group_empty(self):
        app = self.make_application(
            email='juan@bipsu.edu.ph', full_name='Juan Dela Cruz',
            qualified_for='Affirmative', shs_gpa=91.5, suc_exam_score=42.0)
        self.assertEqual(app.affirmative_eligibility.shs_gpa, 91.5)
        self.assertEqual(app.employment.employment_status, '')
        self.assertIsNone(app.employment.years_of_service)

    def test_the_two_programmes_are_still_told_apart_by_a_column(self):
        self.make_application(qualified_for='Staff', status='Approved')
        self.make_application(email='juan@bipsu.edu.ph', full_name='Juan Dela Cruz',
                              qualified_for='Affirmative', status='Approved')
        self.assertEqual(
            ApplicantRecord.objects.filter(
                status='Approved', qualified_for='Staff').count(), 1)
        self.assertEqual(
            ApplicantRecord.objects.filter(
                status='Approved', qualified_for='Affirmative').count(), 1)


class QuerysetsNameTheRelationTest(StaffFactoryMixin, TestCase):
    def test_analytics_still_groups_approved_scholars_by_course(self):
        self.make_application(qualified_for='Staff', status='Approved',
                              course='MA Education')
        self.make_application(email='juan@bipsu.edu.ph', full_name='Juan Dela Cruz',
                              qualified_for='Staff', status='Approved',
                              course='MA Education')
        rows = ApplicantRecord.objects.filter(
            status='Approved', qualified_for='Staff'
        ).values('enrollment__course')
        self.assertEqual([r['enrollment__course'] for r in rows],
                         ['MA Education', 'MA Education'])

    def test_analytics_still_groups_scholars_by_school(self):
        self.make_application(qualified_for='Staff', status='Approved',
                              school='College of Education', course='MA Education')
        rows = ApplicantRecord.objects.filter(
            status='Approved', qualified_for='Staff'
        ).values('enrollment__school', 'enrollment__course')
        self.assertEqual(list(rows), [{'enrollment__school': 'College of Education',
                                       'enrollment__course': 'MA Education'}])

    def test_the_employee_id_clash_check_is_still_one_query(self):
        first = self.make_staff()
        self.make_staff(email='ana@bipsu.edu.ph', employee_id='32-1-000002')
        clash = StaffProfile.objects.filter(employee_id='32-1-213313').exclude(pk=first.pk)
        self.assertFalse(clash.exists())

    def test_with_details_fetches_the_rows_in_one_query(self):
        self.make_application(course='MA Education', gender='Female')
        with self.assertNumQueries(1):
            app = ApplicantRecord.with_details().get(email='maria@bipsu.edu.ph')
            self.assertEqual(app.course, 'MA Education')
            self.assertEqual(app.gender, 'Female')


class UploadedDocumentsStillResolveToTheirOwnerTest(TestCase):
    def setUp(self):
        self.client = Client()

    def _student(self, email='ana@bipsu.edu.ph'):
        user = User.objects.create_user(
            username=email, email=email, password='pw',
            first_name='Ana', last_name='Lim', role='student')
        return StudentProfile.objects.create(user=user, student_id='2022-00111')

    def test_a_student_may_read_their_own_shs_certificate(self):
        profile = self._student()
        profile.shs_gpa_cert = a_document('shs.pdf')
        profile.save()

        from api.media_views import _may_read
        self.assertTrue(_may_read(profile.user, profile.shs_gpa_cert.name))

    def test_a_student_may_read_their_own_suc_certificate(self):
        profile = self._student()
        profile.suc_exam_cert = a_document('suc.pdf')
        profile.save()

        from api.media_views import _may_read
        self.assertTrue(_may_read(profile.user, profile.suc_exam_cert.name))

    def test_another_student_may_not(self):
        owner = self._student()
        owner.shs_gpa_cert = a_document('shs.pdf')
        owner.save()
        other = User.objects.create_user(
            username='b@bipsu.edu.ph', email='b@bipsu.edu.ph', password='pw',
            first_name='Bea', last_name='Cruz', role='student')

        from api.media_views import _may_read
        self.assertFalse(_may_read(other, owner.shs_gpa_cert.name))

    def test_a_staff_member_may_read_their_own_appointment_paper(self):
        user = User.objects.create_user(
            username='maria@bipsu.edu.ph', email='maria@bipsu.edu.ph', password='pw',
            first_name='Maria', last_name='Santos', role='nsu_staff')
        staff = StaffProfile.objects.create(user=user, employee_id='32-1-213313')
        staff.appointment_paper = a_document()
        staff.save()

        from api.media_views import _may_read
        self.assertTrue(_may_read(user, staff.appointment_paper.name))

    def test_an_applicant_may_read_the_certificate_on_their_application(self):
        app = ApplicantRecord.objects.create(
            full_name='Juan Dela Cruz', email='juan@bipsu.edu.ph',
            qualified_for='Affirmative')
        app.shs_certificate = a_document('shs.pdf')
        app.save()
        user = User.objects.create_user(
            username='juan@bipsu.edu.ph', email='juan@bipsu.edu.ph', password='pw',
            first_name='Juan', last_name='Dela Cruz', role='student')

        from api.media_views import _may_read
        self.assertTrue(_may_read(user, app.shs_certificate.name))
