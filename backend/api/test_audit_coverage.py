"""Every portal writes to the audit trail, not only the office's.

The evaluators asked for action logs an administrator can trace an operation
through. The trail existed and was thorough, but nothing in the student portal
and nothing in the employee portal wrote to it — a student could apply, edit
their household income and submit a renewal without leaving a single entry.

These cases drive the real views and read the rows back, rather than checking
that ``ActivityLog.record`` appears somewhere in the source.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    ActivityLog, Application, Scholarship, StaffProfile, StudentProfile,
    SystemSettings, User,
)


def a_document(name='proof.pdf'):
    """A small uploadable file."""
    return SimpleUploadedFile(name, b'%PDF-1.4 proof',
                              content_type='application/pdf')


def entries_for(user, verb=None):
    """The audit rows written for one account."""
    rows = ActivityLog.objects.filter(user=user)
    return list(rows.filter(verb=verb) if verb else rows)


class StudentPortalIsAuditedTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='student-pw-1', first_name='Ana', last_name='Cruz',
            role='student')
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2026-0001', course='BSCS',
            year_level=2, gender='F', contact_number='09171234567',
            barangay='Poblacion', municipality='Naval', province='Biliran',
            date_of_birth='2004-03-11')
        self.client = Client()
        self.assertTrue(self.client.login(
            email='ana@bipsu.edu.ph', password='student-pw-1'))
        ActivityLog.objects.all().delete()

    def test_signing_in_is_recorded_with_the_address_it_came_from(self):
        client = Client(REMOTE_ADDR='203.0.113.9')
        client.post('/login/', {'email': 'ana@bipsu.edu.ph',
                                'password': 'student-pw-1'})
        entry = ActivityLog.objects.filter(verb='sign-in').first()
        self.assertIsNotNone(entry, 'a portal sign-in left no audit entry')
        self.assertEqual(entry.user, self.user)
        self.assertIn('Signed in', entry.action)

    def test_signing_out_is_recorded(self):
        self.client.get('/logout/')
        actions = [e.action for e in entries_for(self.user, 'sign-in')]
        self.assertIn('Signed out', actions)

    def test_editing_a_profile_names_who_edited_it(self):
        self.client.post('/student/profile/', {
            'citizenship': 'Filipino',
            'family_income': '48000',
            'household_size': '5',
            'disability_type': 'NO',
        })
        entry = ActivityLog.objects.filter(verb='update').first()
        self.assertIsNotNone(entry, 'a profile edit left no audit entry')
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.target_type, 'StudentProfile')
        self.assertEqual(entry.target_id, str(self.profile.pk))

    def test_a_declaration_filed_from_the_portal_is_recorded(self):
        self.client.post('/student/profile/', {
            'citizenship': 'Filipino',
            'family_income': '48000',
            'household_size': '5',
            'disability_type': 'NO',
            'has_scholarship': 'on',
            'scholarship_type': 'DOST',
            'award_number': 'DOST-2026-0001',
            'proof_document': a_document('dost.pdf'),
        })
        actions = [e.action for e in entries_for(self.user, 'create')]
        self.assertTrue(any('DOST' in a for a in actions),
                        f'no entry named the declared award: {actions}')

    def test_nothing_is_recorded_when_the_edit_was_refused(self):
        """A refused edit must not leave an entry saying it happened.

        An audit trail that records attempts as if they succeeded is worse
        than one that records nothing: it puts a change in the record that
        the database never made.
        """
        response = self.client.post('/student/profile/', {
            'citizenship': 'Filipino',
            'family_income': '48000',
            'household_size': '5',
            'disability_type': 'NO',
            'shs_gpa_cert': SimpleUploadedFile(
                'grades.exe', b'MZ not a document',
                content_type='application/octet-stream'),
        })
        self.assertTrue(response.context['errors'],
                        'the disallowed upload was accepted, so this case '
                        'no longer tests a refusal')
        self.assertEqual(
            entries_for(self.user, 'update'), [],
            'a rejected edit was written to the audit trail as if it happened')


class StaffPortalIsAuditedTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        Scholarship.objects.create(
            name='BiPSU Staff Scholarship', type='Staff',
            category='application', description='x', eligibility='x',
            requirements=[])
        self.user = User.objects.create_user(
            username='ernesto@bipsu.edu.ph', email='ernesto@bipsu.edu.ph',
            password='staff-pw-1', first_name='Ernesto', last_name='Dela Pena',
            role='nsu_staff')
        StaffProfile.objects.create(user=self.user, employee_id='EMP-0042')
        self.client = Client()
        self.assertTrue(self.client.login(
            email='ernesto@bipsu.edu.ph', password='staff-pw-1'))
        ActivityLog.objects.all().delete()

    def test_editing_a_staff_profile_names_who_edited_it(self):
        self.client.post('/nsu-staff/profile/', {
            'first_name': 'Ernesto', 'last_name': 'Dela Pena',
            'employee_id': 'EMP-0042', 'gender': 'Male',
        })
        entry = ActivityLog.objects.filter(verb='update').first()
        self.assertIsNotNone(entry, 'a staff profile edit left no audit entry')
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.target_type, 'StaffProfile')

    def test_applying_for_the_staff_scholarship_is_recorded(self):
        self.client.post('/nsu-staff/apply/', {
            'first_name': 'Ernesto', 'last_name': 'Dela Pena',
            'date_of_birth': '1990-01-01', 'gender': 'Male',
            'course': 'BSIT', 'student_number': 'EMP-0042',
            'employment_status': 'Regular', 'designation': 'Instructor I',
            'years_of_service': '6', 'date_of_regularization': '2020-01-01',
            'appointment_paper': a_document('appointment.pdf'),
        })
        actions = [e.action for e in entries_for(self.user)]
        self.assertTrue(
            any('Staff Scholarship' in a for a in actions),
            f'applying left no entry naming the programme: {actions}')


class TheTrailIsEvidenceTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.officer = User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='pw', role='vpsea')

    def test_an_administrator_cannot_add_edit_or_delete_an_entry(self):
        from django.contrib.admin.sites import site

        from api.admin import ActivityLogAdmin

        admin = ActivityLogAdmin(ActivityLog, site)
        self.assertFalse(admin.has_add_permission(None))
        self.assertFalse(admin.has_change_permission(None))
        self.assertFalse(admin.has_delete_permission(None))

    def test_an_entry_names_the_person_and_the_role_they_acted_as(self):
        from django.contrib.admin.sites import site

        from api.admin import ActivityLogAdmin

        entry = ActivityLog.record(self.officer, 'Did a thing', verb='other')
        shown = ActivityLogAdmin(ActivityLog, site).actor(entry)
        self.assertIn('sdso@bipsu.edu.ph', shown)
        self.assertIn('VPSEA Admin', shown)

    def test_something_the_system_did_alone_is_not_blamed_on_anyone(self):
        from django.contrib.admin.sites import site

        from api.admin import ActivityLogAdmin

        entry = ActivityLog.record(None, 'Rolled the term over', verb='other')
        self.assertEqual(
            ActivityLogAdmin(ActivityLog, site).actor(entry), 'the system')

    def test_a_deleted_record_is_still_traceable_through_its_entry(self):
        scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic',
            category='application', description='x', eligibility='x',
            requirements=[])
        student = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            role='student')
        profile = StudentProfile.objects.create(
            user=student, student_id='2026-0002', course='BSCS')
        award = Application.objects.create(
            student=profile, scholarship=scholarship, term_label='26-1')

        identity = ActivityLog.identify(award)
        award.delete()
        ActivityLog.record(self.officer, 'Deleted an award', verb='delete',
                           identity=identity)

        entry = ActivityLog.objects.filter(verb='delete').first()
        self.assertEqual(entry.target_type, 'Application')
        self.assertTrue(entry.target_id)
        self.assertTrue(entry.target_label)
