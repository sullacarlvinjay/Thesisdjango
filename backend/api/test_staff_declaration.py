from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.constants import DECLARABLE_SCHOLARSHIP_TYPES, SCHOLARSHIP_TYPE_CHOICES
from api.models import (
    AffirmativeStaffApplication, ScholarshipLinkRequest, StaffProfile,
    StaffScholarshipDeclaration, StudentProfile, SystemSettings, User,
)
from api.test_registration_payload import (
    a_declared_scholar, a_staff_member, a_student,
)


def a_pdf(name='award.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


def register(client, **overrides):
    return client.post('/register/', a_staff_member(**overrides))


class StudentsCannotDeclareTheStaffScholarshipTest(TestCase):
    def test_the_staff_scholarship_is_not_on_the_student_dropdown(self):
        offered = [t for t, _ in DECLARABLE_SCHOLARSHIP_TYPES]
        self.assertNotIn('Staff', offered)
        self.assertNotIn('Affirmative', offered)

    def test_the_programmes_a_student_can_actually_hold_are_all_still_there(self):
        offered = [t for t, _ in DECLARABLE_SCHOLARSHIP_TYPES]
        for stype in ('Academic', 'TDP', 'SUC-TDP', 'DOST', 'JLSS',
                      'CHED', 'CoScho', 'Sports', 'GSIS'):
            self.assertIn(stype, offered, stype)

    def test_the_canonical_type_list_is_left_alone(self):
        self.assertIn('Staff', [t for t, _ in SCHOLARSHIP_TYPE_CHOICES])

    def test_the_registration_page_does_not_offer_it(self):
        html = Client().get('/register/').content.decode()
        self.assertIn('value="Academic"', html)
        self.assertNotIn('value="Staff"', html)

    def test_a_posted_staff_declaration_is_refused_rather_than_stored(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        r = Client().post('/register/', a_declared_scholar(
            first_name='Ana', last_name='Lim',
            email='ana@bipsu.edu.ph', student_id='2022-00111',
            scholarship_type='Staff', proof_document=a_pdf(),
        ))
        self.assertContains(r, 'Say which scholarship you already hold')
        self.assertFalse(ScholarshipLinkRequest.objects.exists())
        self.assertFalse(User.objects.filter(email='ana@bipsu.edu.ph').exists())


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
        self.assertFalse(AffirmativeStaffApplication.objects.exists())

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
        app = AffirmativeStaffApplication.objects.get()
        self.assertEqual(app.qualified_for, 'Staff')
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.email, 'ernesto@bipsu.edu.ph')
        self.assertEqual(app.full_name, 'Ernesto Dela Pena')

    def test_the_award_is_stamped_with_the_active_term(self):
        self._decide('approve')
        app = AffirmativeStaffApplication.objects.get()
        self.assertEqual(app.term_label, '26-1')
        self.assertEqual(app.semester, '1st Semester')

    def test_the_award_carries_the_details_off_the_staff_profile(self):
        self._decide('approve')
        app = AffirmativeStaffApplication.objects.get()
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
        self.assertEqual(decl.linked_application, AffirmativeStaffApplication.objects.get())

    def test_rejecting_the_account_writes_no_award(self):
        self._decide('reject', 'We have no record of that award.')
        self.assertFalse(AffirmativeStaffApplication.objects.exists())
        decl = StaffScholarshipDeclaration.objects.get()
        self.assertEqual(decl.status, 'Rejected')
        self.assertEqual(decl.remarks, 'We have no record of that award.')

    def test_deciding_twice_does_not_leave_the_scholar_counted_twice(self):
        self._decide('approve')
        StaffScholarshipDeclaration.objects.update(status='Pending')
        self._decide('approve', 'Corrected.')
        self.assertEqual(AffirmativeStaffApplication.objects.count(), 1)

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
        self.assertFalse(AffirmativeStaffApplication.objects.filter(
            email='rosa@bipsu.edu.ph').exists())
