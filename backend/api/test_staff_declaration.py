from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.constants import DECLARABLE_SCHOLARSHIP_TYPES, SCHOLARSHIP_TYPE_CHOICES
from api.models import (
    ApplicantRecord, ScholarshipLinkRequest, StaffProfile,
    StaffScholarshipDeclaration, StudentProfile, SystemSettings, User,
)
from api.test_registration_payload import (
    a_declared_scholar, a_staff_member, a_student,
)


def a_pdf(name='award.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


def register(client, **overrides):
    return client.post('/register/', a_staff_member(**overrides))


def a_dependent(**overrides):
    return a_declared_scholar(**dict(
        dict(first_name='Kid', last_name='Duallo',
             email='kid@bipsu.edu.ph', student_id='2026-00111',
             scholarship_type='Staff', proof_document=a_pdf(),
             staff_name='Ernesto Dela Pena',
             staff_employee_id='EMP-0042',
             relationship_to_staff='Son'),
        **overrides))


class StudentsDeclareTheStaffScholarshipAsADependentTest(TestCase):
    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})

    def test_the_staff_scholarship_is_on_the_student_dropdown(self):
        offered = [t for t, _ in DECLARABLE_SCHOLARSHIP_TYPES]
        self.assertIn('Staff', offered)

    def test_affirmative_is_still_off_it(self):
        offered = [t for t, _ in DECLARABLE_SCHOLARSHIP_TYPES]
        self.assertNotIn('Affirmative', offered)

    def test_the_programmes_a_student_can_actually_hold_are_all_still_there(self):
        offered = [t for t, _ in DECLARABLE_SCHOLARSHIP_TYPES]
        for stype in ('Academic', 'TDP', 'SUC-TDP', 'DOST', 'JLSS',
                      'CHED', 'CoScho', 'Sports', 'GSIS'):
            self.assertIn(stype, offered, stype)

    def test_the_canonical_type_list_is_left_alone(self):
        self.assertIn('Staff', [t for t, _ in SCHOLARSHIP_TYPE_CHOICES])

    def test_the_registration_page_offers_it(self):
        html = Client().get('/register/').content.decode()
        self.assertIn('value="Academic"', html)
        self.assertIn('value="Staff"', html)

    def test_the_page_asks_who_the_employee_is(self):
        html = Client().get('/register/').content.decode()
        self.assertIn('name="staff_name"', html)
        self.assertIn('name="staff_employee_id"', html)
        self.assertIn('name="relationship_to_staff"', html)

    def test_a_dependent_declaration_is_stored(self):
        Client().post('/register/', a_dependent())
        req = ScholarshipLinkRequest.objects.get(scholarship_type='Staff')
        self.assertEqual(req.staff_name, 'Ernesto Dela Pena')
        self.assertEqual(req.staff_employee_id, 'EMP-0042')
        self.assertEqual(req.relationship_to_staff, 'Son')

    def test_it_is_refused_without_the_employee_it_hangs_off(self):
        r = Client().post('/register/', a_dependent(staff_employee_id=''))
        self.assertContains(r, 'checks the appointment against it')
        self.assertFalse(ScholarshipLinkRequest.objects.exists())
        self.assertFalse(User.objects.filter(email='kid@bipsu.edu.ph').exists())

    def test_it_is_refused_without_a_relationship(self):
        r = Client().post('/register/', a_dependent(relationship_to_staff=''))
        self.assertContains(r, 'how you are related')
        self.assertFalse(ScholarshipLinkRequest.objects.exists())

    def test_an_invented_relationship_is_refused(self):
        r = Client().post('/register/', a_dependent(relationship_to_staff='Cousin'))
        self.assertContains(r, 'how you are related')
        self.assertFalse(ScholarshipLinkRequest.objects.exists())

    def test_another_programme_is_not_asked_for_an_employee(self):
        Client().post('/register/', a_dependent(
            scholarship_type='DOST', staff_name='', staff_employee_id='',
            relationship_to_staff=''))
        req = ScholarshipLinkRequest.objects.get(scholarship_type='DOST')
        self.assertEqual(req.staff_employee_id, '')

    def test_employee_details_sent_for_another_programme_are_dropped(self):
        Client().post('/register/', a_dependent(scholarship_type='DOST'))
        req = ScholarshipLinkRequest.objects.get(scholarship_type='DOST')
        self.assertEqual(req.staff_name, '')
        self.assertEqual(req.relationship_to_staff, '')


class ApprovingADependentWritesTheStaffLedgerTest(TestCase):
    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        self.reviewer = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            role='vpsea')
        Client().post('/register/', a_dependent())
        self.req = ScholarshipLinkRequest.objects.get(scholarship_type='Staff')

    def _approve(self):
        from api.student_views import approve_declared_scholarship
        return approve_declared_scholarship(self.req, self.reviewer)

    def test_the_award_lands_in_the_applicant_record_not_an_application(self):
        from api.models import Application
        award, error = self._approve()
        self.assertEqual(error, '')
        self.assertIsInstance(award, ApplicantRecord)
        self.assertEqual(award.qualified_for, 'Staff')
        self.assertEqual(award.status, 'Approved')
        self.assertFalse(Application.objects.filter(
            scholarship__type='Staff').exists())

    def test_the_award_is_marked_as_a_dependents(self):
        award, _ = self._approve()
        self.assertTrue(award.is_nsu_dependent)
        self.assertFalse(award.is_nsu_staff)

    def test_the_employee_it_hangs_off_is_carried_across(self):
        award, _ = self._approve()
        self.assertEqual(award.staff_name, 'Ernesto Dela Pena')
        self.assertEqual(award.staff_employee_id, 'EMP-0042')
        self.assertEqual(award.relationship_to_staff, 'Son')

    def test_the_students_own_details_are_carried_across(self):
        award, _ = self._approve()
        self.assertEqual(award.student_id, '2026-00111')

    def test_the_declaration_points_at_what_it_became(self):
        award, _ = self._approve()
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'Approved')
        self.assertEqual(self.req.linked_applicant_record_id, award.pk)
        self.assertIsNone(self.req.linked_application)

    def test_approving_twice_does_not_write_two_awards(self):
        self._approve()
        self._approve()
        self.assertEqual(ApplicantRecord.objects.filter(
            qualified_for='Staff').count(), 1)

    def test_the_ranking_now_sees_a_dependent(self):
        from api.staff_ranking import _standing_rule
        award, _ = self._approve()
        standing, rule = _standing_rule(award)
        self.assertIn('dependent', rule.detail.lower())


class StaffDeclareAtRegistrationTest(TestCase):
    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})

    def test_the_staff_form_offers_the_one_programme_it_can(self):
        html = Client().get('/register/').content.decode()
        self.assertIn('name="has_staff_scholarship"', html)
        self.assertIn('BiPSU Staff Scholarship', html)
        self.assertIn('name="staff_proof_document"', html)

    def test_declaring_it_records_a_pending_declaration(self):
        register(Client(), has_staff_scholarship='on', staff_proof_document=a_pdf(),
                 staff_notes='Awarded last year.')
        decl = StaffScholarshipDeclaration.objects.get()
        self.assertEqual(decl.staff_user.email, 'ernesto@bipsu.edu.ph')
        self.assertEqual(decl.status, 'Pending')
        self.assertEqual(decl.notes, 'Awarded last year.')
        self.assertEqual(decl.term_label, '26-1')

    def test_no_award_exists_until_the_office_says_so(self):
        register(Client(), has_staff_scholarship='on', staff_proof_document=a_pdf())
        self.assertFalse(ApplicantRecord.objects.exists())

    def test_not_declaring_records_nothing(self):
        register(Client())
        self.assertFalse(StaffScholarshipDeclaration.objects.exists())
        self.assertTrue(StaffProfile.objects.filter(
            user__email='ernesto@bipsu.edu.ph').exists())

    def test_declaring_without_proof_is_refused(self):
        r = register(Client(), has_staff_scholarship='on')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(StaffScholarshipDeclaration.objects.exists())
        self.assertFalse(User.objects.filter(email='ernesto@bipsu.edu.ph').exists())

    def test_a_student_registration_is_untouched_by_the_staff_field(self):
        Client().post('/register/', a_student(
            first_name='Ana', last_name='Lim',
            email='ana@bipsu.edu.ph', student_id='2022-00111',
            has_staff_scholarship='on', staff_proof_document=a_pdf(),
        ))
        self.assertTrue(StudentProfile.objects.filter(student_id='2022-00111').exists())
        self.assertFalse(StaffScholarshipDeclaration.objects.exists())


class TheOfficeDecidesItWithTheAccountTest(TestCase):
    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1', 'active_semester': '1st Semester'})
        User.objects.create_user(username='v@bipsu.edu.ph', email='v@bipsu.edu.ph',
                                 password='pw', role='vpsea')
        register(Client(), has_staff_scholarship='on', staff_proof_document=a_pdf(),
                 staff_notes='Awarded last year.')
        self.account = User.objects.get(email='ernesto@bipsu.edu.ph')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def _decide(self, action, message='Checked against our records.'):
        return self.c.post('/vpsea/accounts/', {
            'user_id': self.account.id, 'action': action, 'message': message})

    def test_the_queue_shows_what_was_declared(self):
        html = self.c.get('/vpsea/accounts/').content.decode()
        self.assertIn('BiPSU Staff Scholarship declared at registration', html)
        self.assertIn('Awarded last year.', html)
        self.assertIn('View document', html)

    def test_approving_the_account_records_the_award(self):
        self._decide('approve')
        app = ApplicantRecord.objects.get()
        self.assertEqual(app.qualified_for, 'Staff')
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.email, 'ernesto@bipsu.edu.ph')
        self.assertEqual(app.full_name, 'Ernesto Dela Pena')

    def test_the_award_is_stamped_with_the_active_term(self):
        self._decide('approve')
        app = ApplicantRecord.objects.get()
        self.assertEqual(app.term_label, '26-1')
        self.assertEqual(app.semester, '1st Semester')

    def test_the_award_carries_the_details_off_the_staff_profile(self):
        self._decide('approve')
        app = ApplicantRecord.objects.get()
        self.assertEqual(app.staff_employee_id, 'EMP-0042')
        self.assertEqual(app.department, 'Civil Engineering')
        self.assertEqual(app.position, 'Instructor I')
        self.assertTrue(app.is_nsu_staff)
        self.assertFalse(app.is_nsu_dependent)

    def test_the_declaration_is_marked_decided_and_points_at_the_award(self):
        self._decide('approve')
        decl = StaffScholarshipDeclaration.objects.get()
        self.assertEqual(decl.status, 'Approved')
        self.assertEqual(decl.reviewed_by.email, 'v@bipsu.edu.ph')
        self.assertIsNotNone(decl.reviewed_at)
        self.assertEqual(decl.linked_application, ApplicantRecord.objects.get())

    def test_rejecting_the_account_writes_no_award(self):
        self._decide('reject', 'We have no record of that award.')
        self.assertFalse(ApplicantRecord.objects.exists())
        decl = StaffScholarshipDeclaration.objects.get()
        self.assertEqual(decl.status, 'Rejected')
        self.assertEqual(decl.remarks, 'We have no record of that award.')

    def test_deciding_twice_does_not_leave_the_scholar_counted_twice(self):
        self._decide('approve')
        StaffScholarshipDeclaration.objects.update(status='Pending')
        self._decide('approve', 'Corrected.')
        self.assertEqual(ApplicantRecord.objects.count(), 1)

    def test_an_approved_holder_is_not_asked_to_apply_again(self):
        self._decide('approve')
        staff = Client()
        self.assertTrue(staff.login(email='ernesto@bipsu.edu.ph', password='pw-for-tests'))
        r = staff.get('/nsu-staff/apply/')
        self.assertTrue(r.context['blocked'])
        self.assertIn('already have a Staff Scholarship', r.context['blocked_reason'])

    def test_an_account_with_no_declaration_is_decided_as_before(self):
        other = Client()
        register(other, email='rosa@bipsu.edu.ph', first_name='Rosa')
        account = User.objects.get(email='rosa@bipsu.edu.ph')
        self.c.post('/vpsea/accounts/',
                    {'user_id': account.id, 'action': 'approve', 'message': 'ok'})
        account.refresh_from_db()
        self.assertEqual(account.verification_status, 'approved')
        self.assertFalse(ApplicantRecord.objects.filter(
            email='rosa@bipsu.edu.ph').exists())
