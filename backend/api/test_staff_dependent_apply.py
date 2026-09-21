from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (ApplicantRecord, Scholarship, ScholarshipLinkRequest,
                        StaffProfile, StudentProfile, SystemSettings, User)
from api.views_shared import held_scholarship_types
from api.views_student import _scholarship_records


def _paper():
    return SimpleUploadedFile('appointment.pdf', b'%PDF-1.4 appointment',
                              content_type='application/pdf')


class StaffDependentApplyTest(TestCase):
    """An employee filing the Staff Scholarship for their dependent.

    The dependent is a student, not an employee, so the application carries
    the dependent's name, enrolment and birthday while the appointment behind
    it stays the employee's. Everything here guards one of the two ways that
    can go wrong: the employee's own record being confused with the
    dependent's, and the award landing on the wrong student's account.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
            accepting_applications=True)
        self.employee = User.objects.create_user(
            username='rosa@bipsu.edu.ph', email='rosa@bipsu.edu.ph',
            password='pw', first_name='Rosa', last_name='Delgado',
            role='nsu_staff')
        StaffProfile.objects.create(user=self.employee, employee_id='EMP-0042')
        self.c = Client()
        self.assertTrue(self.c.login(email='rosa@bipsu.edu.ph', password='pw'))

    def _student(self, student_id='2024-00311', dob='2006-04-18',
                 email='child@bipsu.edu.ph', first='Mila', last='Delgado'):
        user = User.objects.create_user(
            username=email, email=email, password='pw',
            first_name=first, last_name=last, role='student')
        return StudentProfile.objects.create(
            user=user, student_id=student_id, course='BSCS', year_level=2,
            date_of_birth=dob)

    def _post(self, **overrides):
        form = dict(
            applicant_kind='dependent',
            first_name='Mila', last_name='Delgado',
            date_of_birth='2006-04-18', gender='Female',
            course='BSCS', year_level='2',
            student_number='2024-00311',
            relationship_to_staff='Daughter',
            employee_number='EMP-0042',
            employment_status='Regular', designation='Teaching',
            years_of_service='11', date_of_regularization='2015-06-01',
            appointment_paper=_paper(),
        )
        form.update(overrides)
        return self.c.post('/nsu-staff/apply/', form)

    def _filed(self):
        return ApplicantRecord.objects.filter(
            qualified_for='Staff',
            staff_eligibility__is_nsu_dependent=True).first()

    def test_the_form_offers_a_dependent_mode(self):
        page = self.c.get('/nsu-staff/apply/').content.decode()
        self.assertIn('name="applicant_kind"', page)
        self.assertIn('value="dependent"', page)

    def test_dependent_mode_asks_for_the_dependents_details(self):
        page = self.c.get(
            '/nsu-staff/apply/?applicant_kind=dependent').content.decode()
        self.assertIn('name="relationship_to_staff"', page)
        self.assertIn('name="employee_number"', page)
        self.assertIn("Dependent's Student Number", page)

    def test_filing_for_a_dependent_links_the_student_account(self):
        profile = self._student()
        self._post()
        record = self._filed()
        self.assertIsNotNone(record, 'no dependent record was written')
        self.assertEqual(record.linked_student_id, profile.pk)
        self.assertEqual(record.email, 'child@bipsu.edu.ph')
        self.assertTrue(record.is_nsu_dependent)
        self.assertFalse(record.is_nsu_staff)
        self.assertEqual(record.staff_name, 'Rosa Delgado')
        self.assertEqual(record.staff_employee_id, 'EMP-0042')
        self.assertEqual(record.relationship_to_staff, 'Daughter')

    def test_the_record_is_never_filed_under_the_employees_email(self):
        self._student()
        self._post()
        self.assertNotEqual(self._filed().email, 'rosa@bipsu.edu.ph')

    def test_a_dependent_with_no_account_is_still_filed_unlinked(self):
        self._post(student_number='2024-99999',
                   dependent_email='nobody@example.com')
        record = self._filed()
        self.assertIsNotNone(record)
        self.assertIsNone(record.linked_student_id)
        self.assertEqual(record.email, 'nobody@example.com')

    def test_a_student_number_with_another_birthday_is_refused(self):
        self._student(dob='2001-01-01')
        self._post()
        self.assertIsNone(
            self._filed(),
            'a mistyped student number attached the award to a stranger')

    def test_the_refusal_names_the_number_rather_than_the_student(self):
        other = self._student(dob='2001-01-01', first='Unrelated',
                              last='Stranger')
        page = self._post().content.decode()
        self.assertIn('2024-00311', page)
        self.assertNotIn(other.user.get_full_name(), page)

    def test_a_dependent_does_not_consume_the_employees_own_application(self):
        self._student()
        self._post()
        page = self.c.get('/nsu-staff/apply/').content.decode()
        self.assertNotIn('You already have a Staff Scholarship application',
                         page)

    def test_an_employee_with_their_own_application_may_still_file_for_one(self):
        ApplicantRecord.objects.create(
            full_name='Rosa Delgado', email='rosa@bipsu.edu.ph',
            qualified_for='Staff', status='Pending Validation',
            course='BSIT', year_level=1, is_nsu_staff=True,
            school_year='2026-2027', semester='2nd Semester',
            term_label='26-2')
        self._student()
        self._post()
        self.assertIsNotNone(
            self._filed(),
            "the employee's own pending record blocked their dependent's")

    def test_the_employees_profile_keeps_its_own_details(self):
        self._student()
        self._post(barangay='Somewhere Else', municipality='Naval')
        staff = StaffProfile.objects.get(user=self.employee)
        self.assertNotEqual(staff.barangay, 'Somewhere Else')
        self.assertEqual(staff.employee_id, 'EMP-0042')
        self.assertEqual(staff.employment_status, 'Regular')

    def test_a_dependent_already_declared_by_the_student_is_refused(self):
        profile = self._student()
        ScholarshipLinkRequest.objects.create(
            student=profile, scholarship_type='Staff', term_label='26-2',
            proof_document=SimpleUploadedFile('p.pdf', b'%PDF-1.4 proof',
                                              content_type='application/pdf'),
            status='Pending')
        self._post()
        self.assertIsNone(
            self._filed(),
            'the same award was filed twice through two different doors')

    def test_the_same_dependent_cannot_be_filed_twice(self):
        self._student()
        self._post()
        self._post()
        self.assertEqual(
            ApplicantRecord.objects.filter(
                qualified_for='Staff',
                staff_eligibility__is_nsu_dependent=True).count(), 1)

    def test_a_missing_relationship_is_refused(self):
        self._student()
        self._post(relationship_to_staff='')
        self.assertIsNone(self._filed())

    def test_the_employee_sees_the_dependent_on_their_applications_page(self):
        self._student()
        self._post()
        page = self.c.get('/nsu-staff/applications/').content.decode()
        self.assertIn('Mila Delgado', page)
        self.assertIn('2024-00311', page)


class DependentRecordOnTheStudentPortalTest(TestCase):
    """What the dependent sees once an employee has filed for them."""

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})
        self.student_user = User.objects.create_user(
            username='mila@bipsu.edu.ph', email='mila@bipsu.edu.ph',
            password='pw', first_name='Mila', last_name='Delgado',
            role='student')
        self.profile = StudentProfile.objects.create(
            user=self.student_user, student_id='2024-00311', course='BSCS',
            year_level=2, date_of_birth='2006-04-18')

    def _record(self, status='Pending Validation'):
        record = ApplicantRecord.objects.create(
            full_name='Mila Delgado', email='mila@bipsu.edu.ph',
            qualified_for='Staff', status=status, course='BSCS', year_level=2,
            school_year='2026-2027', semester='2nd Semester',
            term_label='26-2', linked_student=self.profile)
        record.is_nsu_dependent = True
        record.staff_name = 'Rosa Delgado'
        record.student_id = '2024-00311'
        record.save()
        return record

    def test_the_award_appears_on_their_file(self):
        self._record()
        names = [r['name'] for r in _scholarship_records(self.profile)]
        self.assertIn('Staff', [r['type']
                                for r in _scholarship_records(self.profile)])
        self.assertTrue(names)

    def test_the_note_says_who_filed_it(self):
        self._record()
        note = [r['note'] for r in _scholarship_records(self.profile)
                if r['type'] == 'Staff'][0]
        self.assertIn('Rosa Delgado', note)

    def test_an_approved_one_bars_a_second_programme(self):
        self._record(status='Approved')
        self.assertIn('Staff', held_scholarship_types(self.profile))

    def test_one_still_under_review_does_not_bar_anything(self):
        self._record()
        self.assertNotIn('Staff', held_scholarship_types(self.profile))

    def test_another_students_record_is_not_theirs(self):
        other_user = User.objects.create_user(
            username='someone@bipsu.edu.ph', email='someone@bipsu.edu.ph',
            password='pw', role='student')
        other = StudentProfile.objects.create(
            user=other_user, student_id='2024-00999', course='BSIT',
            year_level=1)
        self._record(status='Approved')
        self.assertNotIn('Staff', held_scholarship_types(other))


class DependentRecordClaimedAtRegistrationTest(TestCase):
    """A record filed before the dependent had an account."""

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})

    def _unclaimed(self, student_id='2024-00311', dob='2006-04-18'):
        record = ApplicantRecord.objects.create(
            full_name='Mila Delgado', email='', qualified_for='Staff',
            status='Pending Validation', course='BSCS', year_level=2,
            school_year='2026-2027', semester='2nd Semester',
            term_label='26-2')
        record.is_nsu_dependent = True
        record.staff_name = 'Rosa Delgado'
        record.student_id = student_id
        record.date_of_birth = dob
        record.save()
        return record

    def _profile(self, student_id='2024-00311', dob='2006-04-18'):
        user = User.objects.create_user(
            username='mila@bipsu.edu.ph', email='mila@bipsu.edu.ph',
            password='pw', first_name='Mila', last_name='Delgado',
            role='student')
        return StudentProfile.objects.create(
            user=user, student_id=student_id, course='BSCS', year_level=2,
            date_of_birth=dob)

    def test_registering_with_that_number_claims_it(self):
        from api.views_auth import _claim_records_filed_for
        record = self._unclaimed()
        profile = self._profile()
        self.assertEqual(_claim_records_filed_for(profile), 1)
        record.refresh_from_db()
        self.assertEqual(record.linked_student_id, profile.pk)
        self.assertEqual(record.email, 'mila@bipsu.edu.ph')

    def test_a_different_birthday_does_not_claim_it(self):
        from api.views_auth import _claim_records_filed_for
        record = self._unclaimed()
        profile = self._profile(dob='1999-12-31')
        self.assertEqual(_claim_records_filed_for(profile), 0)
        record.refresh_from_db()
        self.assertIsNone(record.linked_student_id)

    def test_a_different_number_does_not_claim_it(self):
        from api.views_auth import _claim_records_filed_for
        record = self._unclaimed()
        profile = self._profile(student_id='2024-00999')
        self.assertEqual(_claim_records_filed_for(profile), 0)
        record.refresh_from_db()
        self.assertIsNone(record.linked_student_id)

class TheOfficeCanTellADependentApartTest(TestCase):
    """What the SDSO sees when a dependent's application reaches them.

    A dependent's row carries the dependent's name beside the employee's
    appointment. Without something saying so on screen, the office is
    approving a regular appointment against a name that does not hold one.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
            accepting_applications=True)
        self.office = User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='pw', first_name='Office', last_name='Staff',
            role='vpsea')
        self.student_user = User.objects.create_user(
            username='mila@bipsu.edu.ph', email='mila@bipsu.edu.ph',
            password='pw', first_name='Mila', last_name='Delgado',
            role='student')
        self.profile = StudentProfile.objects.create(
            user=self.student_user, student_id='2024-00311', course='BSCS',
            year_level=2, date_of_birth='2006-04-18')
        self.record = ApplicantRecord.objects.create(
            full_name='Mila Delgado', email='mila@bipsu.edu.ph',
            qualified_for='Staff', status='Pending Validation', course='BSCS',
            year_level=2, school_year='2026-2027', semester='2nd Semester',
            term_label='26-2', linked_student=self.profile)
        self.record.is_nsu_dependent = True
        self.record.staff_name = 'Rosa Delgado'
        self.record.staff_employee_id = 'EMP-0042'
        self.record.relationship_to_staff = 'Daughter'
        self.record.employment_status = 'Regular'
        self.record.save()
        self.c = Client()
        self.assertTrue(self.c.login(email='sdso@bipsu.edu.ph', password='pw'))

    def test_the_review_table_names_the_employee_behind_it(self):
        page = self.c.get('/vpsea/affirmative/?tab=staff').content.decode()
        self.assertIn('Rosa Delgado', page)
        self.assertIn('EMP-0042', page)
        self.assertIn('Daughter', page)

    def test_a_decision_reaches_the_students_own_portal(self):
        from api.models import Notification

        self.c.post('/vpsea/affirmative/', {
            'app_id': self.record.id, 'tab': 'staff',
            'status': 'Approved', 'remarks': ''})
        self.assertTrue(
            Notification.objects.filter(student=self.profile).exists(),
            'the decision was emailed but never reached their portal')
