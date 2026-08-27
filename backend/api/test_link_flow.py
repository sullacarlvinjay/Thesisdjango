"""End-to-end check of the import -> register -> link -> approve merge.

Runs against a throwaway test database, so db.sqlite3 is never touched.
    python manage.py test --keepdb=0  (invoked via a TestCase below)
"""
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile

from api.models import (
    User, StudentProfile, Scholarship, Application, ImportedScholar,
    ScholarshipLinkRequest, SystemSettings, Notification,
)


class LinkScholarshipMergeTest(TestCase):
    def setUp(self):
        s = SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        self.label = s.academic_year
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[],
        )
        # 1. VPSEA imports the scholar from the office's Excel file.
        self.archive = ImportedScholar.objects.create(
            scholarship_type='Academic', term_label=self.label,
            last_name='Dela Cruz', first_name='Juan', middle_name='S',
            course='BSCS', year_level=3, gwa=1.25, student_id='2022-0001',
            barangay='Poblacion', municipality='Naval', province='Biliran',
            award_number='AW-99', imported_from='Academic_26-1.xlsx',
        )
        # 2. The student registers their own account afterwards.
        self.student_user = User.objects.create_user(
            username='juan@bipsu.edu.ph', email='juan@bipsu.edu.ph', password='pw',
            first_name='Juan', last_name='Dela Cruz', role='student',
        )
        self.profile = StudentProfile.objects.create(
            user=self.student_user, student_id='2022-0001', course='', year_level=1,
        )
        self.vpsea = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph', password='pw',
            role='vpsea',
        )

    def _submit_link(self, client, stype='Academic', name='award.pdf', size=1024):
        return client.post('/student/link-scholarship/', {
            'scholarship_type': stype,
            'award_number': 'AW-99',
            'notes': 'DOST award letter attached',
            'proof_document': SimpleUploadedFile(name, b'x' * size, content_type='application/pdf'),
        })

    def test_import_register_link_approve_merges_without_duplicating(self):
        c = Client()
        self.assertTrue(c.login(email='juan@bipsu.edu.ph', password='pw'))

        # 3. Student submits the link request.
        r = self._submit_link(c)
        self.assertEqual(r.status_code, 302)
        req = ScholarshipLinkRequest.objects.get()
        self.assertEqual(req.status, 'Pending')
        self.assertEqual(req.term_label, self.label)
        self.assertEqual(req.award_number, 'AW-99')

        # Duplicate submissions are refused while one is pending.
        r = self._submit_link(c)
        self.assertContains(r, 'pending link request')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 1)

        # 4. VPSEA sees it in the queue with the imported row offered as a match.
        a = Client()
        self.assertTrue(a.login(email='vpsea@bipsu.edu.ph', password='pw'))
        r = a.get('/vpsea/link-requests/')
        self.assertEqual(r.status_code, 200)
        rows = r.context['rows']
        self.assertEqual(len(rows), 1)
        self.assertEqual([x.id for x in rows[0]['candidates']], [self.archive.id])

        # Archives before approval: the imported row, and no live scholar.
        r = a.get('/vpsea/archives/?type=Academic')
        self.assertEqual(r.context['total'], 1)
        self.assertEqual(r.context['imported_rows'].count(), 1)
        self.assertEqual(r.context['scholars'].count(), 0)

        # 5. VPSEA approves and merges the imported row.
        r = a.post('/vpsea/link-requests/', {
            'request_id': req.id, 'action': 'approve',
            'archive_id': self.archive.id, 'remarks': 'Verified vs COR',
        })
        self.assertEqual(r.status_code, 302)

        req.refresh_from_db()
        self.archive.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(req.status, 'Approved')
        self.assertEqual(req.reviewed_by, self.vpsea)
        self.assertIsNotNone(req.reviewed_at)
        self.assertEqual(req.matched_archive_id, self.archive.id)
        self.assertEqual(self.archive.claimed_by_id, self.profile.id)

        # The link became a real Approved Application for the active semester.
        app = Application.objects.get()
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.student_id, self.profile.id)
        self.assertEqual(app.source, 'link')
        self.assertEqual(app.school_year, '2026-2027')
        self.assertEqual(app.semester, '1st Semester')
        self.assertEqual(app.term_label, '26-1')
        self.assertEqual(req.linked_application_id, app.id)

        # Blank profile fields were backfilled from the office's import.
        self.assertEqual(self.profile.course, 'BSCS')
        self.assertEqual(self.profile.year_level, 3)
        self.assertEqual(self.profile.gwa, 1.25)
        self.assertEqual(self.profile.municipality, 'Naval')

        # 6. The archives now show ONE entry, not two.
        r = a.get('/vpsea/archives/?type=Academic')
        self.assertEqual(r.context['total'], 1)
        self.assertEqual(r.context['imported_rows'].count(), 0)
        self.assertEqual(r.context['scholars'].count(), 1)

        # The student was notified and the page reflects the link.
        n = Notification.objects.get(student=self.profile)
        self.assertEqual(n.type, 'success')
        r = c.get('/student/link-scholarship/')
        self.assertContains(r, 'already linked to this account')

    def test_reject_requires_a_reason_and_notifies_the_student(self):
        c = Client()
        c.login(email='juan@bipsu.edu.ph', password='pw')
        self._submit_link(c)
        req = ScholarshipLinkRequest.objects.get()

        a = Client()
        a.login(email='vpsea@bipsu.edu.ph', password='pw')
        r = a.post('/vpsea/link-requests/', {'request_id': req.id, 'action': 'reject', 'remarks': ''})
        self.assertIn('reason+is+required', r['Location'])
        req.refresh_from_db()
        self.assertEqual(req.status, 'Pending')

        a.post('/vpsea/link-requests/', {
            'request_id': req.id, 'action': 'reject', 'remarks': 'Proof is unreadable',
        })
        req.refresh_from_db()
        self.assertEqual(req.status, 'Rejected')
        self.assertEqual(req.remarks, 'Proof is unreadable')
        self.assertEqual(Application.objects.count(), 0)
        self.assertEqual(Notification.objects.get(student=self.profile).type, 'warning')

        # Rejected is not blocking: the student may try again with better proof.
        r = c.get('/student/link-scholarship/')
        self.assertContains(r, 'Why it was rejected')
        self.assertContains(r, 'Submit Link Request')

    def test_proof_upload_is_validated_server_side(self):
        c = Client()
        c.login(email='juan@bipsu.edu.ph', password='pw')
        r = self._submit_link(c, name='virus.exe')
        self.assertContains(r, 'Unsupported file type')
        r = self._submit_link(c, size=6 * 1024 * 1024)
        self.assertContains(r, 'too large')
        r = c.post('/student/link-scholarship/', {'scholarship_type': 'Academic'})
        self.assertContains(r, 'Proof document is required.')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 0)

    def test_staff_type_is_a_single_canonical_key(self):
        from api.models import SCHOLARSHIP_TYPE_CHOICES
        keys = [k for k, _ in SCHOLARSHIP_TYPE_CHOICES]
        self.assertIn('Staff', keys)
        self.assertNotIn('NSU Staff', keys)

        Scholarship.objects.create(
            name='BiPSU Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
        )
        c = Client()
        c.login(email='juan@bipsu.edu.ph', password='pw')
        # The old 'NSU Staff' value is rejected; the canonical 'Staff' is accepted.
        r = self._submit_link(c, stype='NSU Staff')
        self.assertContains(r, 'Please select a scholarship type.')
        r = self._submit_link(c, stype='Staff')
        self.assertEqual(r.status_code, 302)
        req = ScholarshipLinkRequest.objects.get()
        self.assertEqual(req.scholarship_type, 'Staff')
        self.assertEqual(req.get_scholarship_type_display(), 'BiPSU Staff Scholarship')

        # Approving finds the 'Staff' program that the archives already use.
        a = Client()
        a.login(email='vpsea@bipsu.edu.ph', password='pw')
        a.post('/vpsea/link-requests/', {'request_id': req.id, 'action': 'approve', 'remarks': 'ok'})
        req.refresh_from_db()
        self.assertEqual(req.status, 'Approved')
        self.assertEqual(req.linked_application.scholarship.type, 'Staff')

    def test_past_semester_rows_are_evidence_only(self):
        old = ImportedScholar.objects.create(
            scholarship_type='Academic', term_label='25-2',
            last_name='Dela Cruz', first_name='Juan', student_id='2022-0001',
        )
        c = Client()
        c.login(email='juan@bipsu.edu.ph', password='pw')
        self._submit_link(c)
        req = ScholarshipLinkRequest.objects.get()

        a = Client()
        a.login(email='vpsea@bipsu.edu.ph', password='pw')
        row = a.get('/vpsea/link-requests/').context['rows'][0]
        self.assertEqual([x.id for x in row['candidates']], [self.archive.id])
        self.assertEqual([x.id for x in row['other_semesters']], [old.id])

        # A past-semester row cannot be claimed, so history is never rewritten.
        r = a.post('/vpsea/link-requests/', {
            'request_id': req.id, 'action': 'approve', 'archive_id': old.id, 'remarks': 'x',
        })
        self.assertIn('no+longer+available', r['Location'])
        old.refresh_from_db()
        self.assertIsNone(old.claimed_by_id)
        self.assertEqual(ScholarshipLinkRequest.objects.get().status, 'Pending')
