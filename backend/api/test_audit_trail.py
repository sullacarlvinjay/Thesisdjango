from django.test import Client, TestCase

from api.models import ActivityLog, StudentProfile, SystemSettings, User


class AuditEntryShapeTest(TestCase):
    """``ActivityLog.record`` has to capture more than a sentence.

    A free-text line can say that something was approved. It cannot say which
    record, what the value was beforehand, or where the request came from, so
    it cannot answer the questions an audit asks.
    """

    def setUp(self):
        self.officer = User.objects.create_user(
            username='office@bipsu.edu.ph', email='office@bipsu.edu.ph',
            password='pw', first_name='R', last_name='B', role='vpsea')
        self.subject = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student')

    def test_it_records_who_what_and_which_record(self):
        entry = ActivityLog.record(
            self.officer, 'Approved the account', verb='approve',
            target=self.subject)
        self.assertEqual(entry.user, self.officer)
        self.assertEqual(entry.verb, 'approve')
        self.assertEqual(entry.target_type, 'User')
        self.assertEqual(entry.target_id, str(self.subject.pk))
        self.assertEqual(
            entry.target_label, str(self.subject),
            'the entry does not name the record in a form a reader '
            'recognises, only by primary key')

    def test_the_record_survives_the_row_it_describes_being_deleted(self):
        entry = ActivityLog.record(
            self.officer, 'Deleted the account', verb='delete',
            target=self.subject)
        subject_id = str(self.subject.pk)
        self.subject.delete()
        entry.refresh_from_db()
        self.assertEqual(
            entry.target_id, subject_id,
            'the audit entry lost its subject when the row went, which is '
            'precisely the case a deletion audit exists for')

    def test_it_keeps_the_callers_address_when_a_request_is_given(self):
        from django.test import RequestFactory
        request = RequestFactory().post('/vpsea/accounts/', REMOTE_ADDR='10.2.3.4')
        entry = ActivityLog.record(self.officer, 'Did a thing', request=request)
        self.assertEqual(entry.ip_address, '10.2.3.4')

    def test_an_entry_without_a_request_simply_has_no_address(self):
        entry = ActivityLog.record(self.officer, 'Did a thing')
        self.assertIsNone(entry.ip_address)

    def test_diff_reports_only_the_fields_that_moved(self):
        moved = ActivityLog.diff(
            {'status': 'pending', 'course': 'BSCS'},
            {'status': 'approved', 'course': 'BSCS'},
            ['status', 'course'])
        self.assertEqual(moved, {'status': ['pending', 'approved']})

    def test_snapshot_reads_the_fields_named(self):
        taken = ActivityLog.snapshot(self.subject, ['email', 'role'])
        self.assertEqual(taken, {'email': 'ana@bipsu.edu.ph', 'role': 'student'})


class AccountDecisionIsAuditedTest(TestCase):
    """Approving or rejecting an account is the decision most worth tracing."""

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        User.objects.create_user(
            username='office@bipsu.edu.ph', email='office@bipsu.edu.ph',
            password='pw', first_name='Rosario', last_name='Bayhon',
            role='vpsea')
        self.applicant = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student',
            verification_status='pending')
        StudentProfile.objects.create(
            user=self.applicant, student_id='2022-00111', course='BSCS',
            year_level=2)
        self.c = Client()
        self.assertTrue(self.c.login(email='office@bipsu.edu.ph', password='pw'))

    def _decide(self, action, message=''):
        return self.c.post('/vpsea/accounts/', {
            'user_id': self.applicant.id, 'action': action,
            'message': message or 'Checked against the enrolment list.'},
            REMOTE_ADDR='10.9.9.9')

    def _entry(self):
        return ActivityLog.objects.filter(
            target_type='User', target_id=str(self.applicant.pk)).first()

    def test_an_approval_is_filed_against_the_account_it_decided(self):
        self._decide('approve')
        entry = self._entry()
        self.assertIsNotNone(entry, 'the approval left no audit entry')
        self.assertEqual(entry.verb, 'approve')
        self.assertEqual(entry.user.email, 'office@bipsu.edu.ph')

    def test_a_rejection_is_filed_as_a_rejection(self):
        self._decide('reject', 'Student number is not on the enrolment list.')
        self.assertEqual(self._entry().verb, 'reject')

    def test_the_entry_carries_the_status_before_and_after(self):
        self._decide('approve')
        self.assertEqual(
            self._entry().changes.get('verification_status'),
            ['pending', 'approved'],
            'the entry does not say what the value was beforehand')

    def test_the_entry_carries_the_address_the_decision_came_from(self):
        self._decide('approve')
        self.assertEqual(self._entry().ip_address, '10.9.9.9')

    def test_every_decision_on_one_account_can_be_listed(self):
        self._decide('approve')
        self._decide('reject', 'Withdrew.')
        found = ActivityLog.objects.filter(
            target_type='User', target_id=str(self.applicant.pk))
        self.assertGreaterEqual(
            found.count(), 2,
            'the history of one account cannot be queried, only searched '
            'through as free text')
