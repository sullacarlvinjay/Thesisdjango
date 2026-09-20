from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    AcademicRenewal, ActivityLog, ApplicantRecord, Application, Scholarship,
    StudentProfile, SystemSettings, User,
)


def an_officer(email, first='Rosa', last='Bello'):
    return User.objects.create_user(
        username=email, email=email, password='pw', role='vpsea',
        first_name=first, last_name=last)


def a_student(email='applicant@bipsu.edu.ph', sid='2024-0001'):
    user = User.objects.create_user(
        username=email, email=email, password='pw',
        first_name='Juan', last_name='Cruz', role='student')
    return StudentProfile.objects.create(
        user=user, student_id=sid, course='BSCS', year_level=2, gwa=1.4)


class ADecisionNamesTheOfficerWhoMadeItTest(TestCase):
    """A verdict without an author cannot be audited.

    While the office was one login this was a detail. It stops being one the
    moment a second officer can sign in: 'the office approved it' then names
    nobody, and no later question about a decision has an answer.
    """

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        self.rosa = an_officer('rosa@bipsu.edu.ph', 'Rosa', 'Bello')
        self.mila = an_officer('mila@bipsu.edu.ph', 'Mila', 'Cruz')
        self.student = a_student()
        self.c = Client()
        self.c.force_login(self.mila)

    def test_an_application_records_which_officer_decided_it(self):
        app = Application.objects.create(
            student=self.student, scholarship=self.scholarship,
            status='Pending Validation', term_label='26-1')

        self.c.post('/vpsea/affirmative/', {
            'app_id': app.id, 'status': 'Approved', 'remarks': 'ok',
            'tab': 'academic'})

        app.refresh_from_db()
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.reviewed_by, self.mila)
        self.assertIsNotNone(app.reviewed_at)

    def test_the_officer_who_did_not_decide_it_is_not_named(self):
        app = Application.objects.create(
            student=self.student, scholarship=self.scholarship,
            status='Pending Validation', term_label='26-1')

        self.c.post('/vpsea/affirmative/', {
            'app_id': app.id, 'status': 'Approved', 'remarks': '',
            'tab': 'academic'})

        app.refresh_from_db()
        self.assertNotEqual(app.reviewed_by, self.rosa)

    def test_an_application_decision_is_written_to_the_audit_trail(self):
        app = Application.objects.create(
            student=self.student, scholarship=self.scholarship,
            status='Pending Validation', term_label='26-1')

        self.c.post('/vpsea/affirmative/', {
            'app_id': app.id, 'status': 'Rejected', 'remarks': 'incomplete',
            'tab': 'academic'})

        entry = ActivityLog.objects.filter(target_type='Application').latest(
            'created_at')
        self.assertEqual(entry.user, self.mila)
        self.assertEqual(entry.verb, 'reject')
        self.assertEqual(entry.target_id, str(app.pk))
        self.assertEqual(entry.changes['status'],
                         ['Pending Validation', 'Rejected'])

    def test_needs_revision_is_neither_an_approval_nor_a_rejection(self):
        app = Application.objects.create(
            student=self.student, scholarship=self.scholarship,
            status='Pending Validation', term_label='26-1')

        self.c.post('/vpsea/affirmative/', {
            'app_id': app.id, 'status': 'Needs Revision', 'remarks': 'redo',
            'tab': 'academic'})

        entry = ActivityLog.objects.filter(target_type='Application').latest(
            'created_at')
        self.assertEqual(entry.verb, 'update')

    def test_a_staff_applicant_record_records_its_officer_too(self):
        record = ApplicantRecord.objects.create(
            full_name='Ana Lim', email='ana@bipsu.edu.ph',
            qualified_for='Staff', status='Pending Validation',
            term_label='26-1')

        self.c.post('/vpsea/affirmative/', {
            'app_id': record.id, 'status': 'Approved', 'remarks': '',
            'tab': 'staff'})

        record.refresh_from_db()
        self.assertEqual(record.reviewed_by, self.mila)
        self.assertIsNotNone(record.reviewed_at)

    def test_a_renewal_records_its_officer_too(self):
        renewal = AcademicRenewal.objects.create(
            student=self.student, scholarship_type='Academic',
            certificate_of_grades=SimpleUploadedFile('cog.pdf', b'%PDF-1.4'),
            certificate_of_enrollment=SimpleUploadedFile('coe.pdf', b'%PDF-1.4'),
            status='Pending', term_label='26-1')

        self.c.post('/vpsea/renewals/', {
            'renewal_id': renewal.id, 'status': 'Approved', 'remarks': 'ok'})

        renewal.refresh_from_db()
        self.assertEqual(renewal.status, 'Approved')
        self.assertEqual(renewal.reviewed_by, self.mila)
        self.assertIsNotNone(renewal.reviewed_at)

    def test_two_officers_deciding_are_told_apart(self):
        mine = Application.objects.create(
            student=self.student, scholarship=self.scholarship,
            status='Pending Validation', term_label='26-1')
        theirs = Application.objects.create(
            student=a_student('second@bipsu.edu.ph', '2024-0002'),
            scholarship=self.scholarship,
            status='Pending Validation', term_label='26-1')

        self.c.post('/vpsea/affirmative/', {
            'app_id': mine.id, 'status': 'Approved', 'remarks': '',
            'tab': 'academic'})
        hers = Client()
        hers.force_login(self.rosa)
        hers.post('/vpsea/affirmative/', {
            'app_id': theirs.id, 'status': 'Rejected', 'remarks': 'no',
            'tab': 'academic'})

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.reviewed_by, self.mila)
        self.assertEqual(theirs.reviewed_by, self.rosa)

    def test_the_page_shows_who_decided_rather_than_only_the_verdict(self):
        app = Application.objects.create(
            student=self.student, scholarship=self.scholarship,
            status='Pending Validation', term_label='26-1')
        self.c.post('/vpsea/affirmative/', {
            'app_id': app.id, 'status': 'Approved', 'remarks': '',
            'tab': 'academic'})

        watching = Client()
        watching.force_login(self.rosa)
        page = watching.get('/vpsea/affirmative/?tab=academic').content.decode()
        self.assertIn(
            'Mila Cruz', page,
            'the other officer reads the verdict without being told whose it is')

    def test_an_undecided_application_names_nobody(self):
        Application.objects.create(
            student=self.student, scholarship=self.scholarship,
            status='Pending Validation', term_label='26-1')

        watching = Client()
        watching.force_login(self.rosa)
        page = watching.get('/vpsea/affirmative/?tab=academic').content.decode()
        self.assertNotIn('Mila Cruz', page)


class TheSuperRoleIsGoneTest(TestCase):
    """A role the portal never routed, which the API still trusted."""

    def test_no_account_can_be_given_it(self):
        from api.constants import USER_ROLES

        self.assertNotIn('super', dict(USER_ROLES))

    def test_the_office_is_the_only_role_the_api_treats_as_the_office(self):
        from api.media_views import OFFICE_ROLES as MEDIA_ROLES
        from api.views import OFFICE_ROLES as API_ROLES

        self.assertEqual(set(API_ROLES), {'vpsea'})
        self.assertEqual(set(MEDIA_ROLES), {'vpsea'})

    def test_every_role_that_can_sign_in_lands_on_a_page_that_exists(self):
        from api.constants import USER_ROLES
        from api.views_auth import PORTAL_FOR_ROLE

        for role, _label in USER_ROLES:
            path = PORTAL_FOR_ROLE.get(role)
            self.assertIsNotNone(path, f'{role} has no portal to land on')
            self.assertNotEqual(
                Client().get(path).status_code, 404,
                f'{role} signs in and lands on a page that does not exist')
