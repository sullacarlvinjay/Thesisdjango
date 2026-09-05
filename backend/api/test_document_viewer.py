"""Uploaded documents open in the shared overlay, not a new tab."""
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client

from api.models import (
    AcademicRenewal, Application, ApplicationDocument, Scholarship,
    ScholarshipLinkRequest, StudentProfile, SystemSettings, User,
)


def _upload(name='proof.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


class DocumentViewerTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        self.scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[],
        )
        self.student_user = User.objects.create_user(
            username='juan@bipsu.edu.ph', email='juan@bipsu.edu.ph', password='pw',
            first_name='Juan', last_name='Dela Cruz', role='student',
        )
        self.profile = StudentProfile.objects.create(
            user=self.student_user, student_id='2024-0001', course='BSCS', year_level=2,
        )
        self.vpsea = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph', password='pw',
            role='vpsea',
        )

    # ── The viewer itself ───────────────────────────────────────────────────
    def test_every_page_carries_the_viewer(self):
        c = Client()
        c.login(email='juan@bipsu.edu.ph', password='pw')
        r = c.get('/student/applications/')
        self.assertContains(r, 'id="docViewer"')
        self.assertContains(r, 'window.openDoc')
        self.assertContains(r, "a[data-doc]")

    def test_media_may_be_framed_by_our_own_pages(self):
        c = Client()
        c.login(email='juan@bipsu.edu.ph', password='pw')
        r = c.get('/student/applications/')
        # Django defaults to DENY, which would blank the viewer's iframe.
        self.assertEqual(r.headers.get('X-Frame-Options'), 'SAMEORIGIN')

    # ── Each surface that shows a document ──────────────────────────────────
    def test_student_application_documents_use_the_overlay(self):
        app = Application.objects.create(
            student=self.profile, scholarship=self.scholarship, status='Approved',
            form_data={},
        )
        ApplicationDocument.objects.create(
            application=app, name='Certificate Of Grades', file=_upload('cog.pdf'))

        c = Client()
        c.login(email='juan@bipsu.edu.ph', password='pw')
        r = c.get('/student/applications/')
        self.assertContains(r, 'data-doc="Certificate Of Grades"')
        self.assertEqual(r.content.decode().count('target="_blank"'), 1,
                         "only the viewer's own Open-in-new-tab control may use it")

    def test_declared_scholarship_proof_uses_the_overlay(self):
        """The proof arrives with the registration and is read on the queue
        that decides it — there is no separate link-request page any more."""
        self.student_user.verification_status = 'pending'
        self.student_user.save(update_fields=['verification_status'])
        ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='DOST',
            proof_document=_upload('award.pdf'), term_label='26-1',
        )
        c = Client()
        c.login(email='vpsea@bipsu.edu.ph', password='pw')
        r = c.get('/vpsea/accounts/')
        self.assertContains(r, 'data-doc="DOST Scholarship — proof"')
        self.assertEqual(r.content.decode().count('target="_blank"'), 1,
                         "only the viewer's own Open-in-new-tab control may use it")

    def test_vpsea_renewal_certificates_use_the_overlay(self):
        AcademicRenewal.objects.create(
            student=self.profile,
            certificate_of_grades=_upload('cog.pdf'),
            certificate_of_enrollment=_upload('coe.pdf'),
        )
        c = Client()
        c.login(email='vpsea@bipsu.edu.ph', password='pw')
        r = c.get('/vpsea/renewals/')
        self.assertContains(r, 'Certificate of Grades')
        self.assertContains(r, 'Certificate of Enrollment')
        self.assertEqual(r.content.decode().count('target="_blank"'), 1,
                         "only the viewer's own Open-in-new-tab control may use it")

    def test_student_profile_certificates_use_the_overlay(self):
        self.profile.shs_gpa_cert = _upload('shs.pdf')
        self.profile.suc_exam_cert = _upload('suc.png')
        self.profile.save()
        c = Client()
        c.login(email='juan@bipsu.edu.ph', password='pw')
        r = c.get('/student/profile/')
        self.assertContains(r, 'data-doc="SHS GPA Certificate"')
        self.assertContains(r, 'data-doc="SUC Exam Certificate"')
        self.assertEqual(r.content.decode().count('target="_blank"'), 1,
                         "only the viewer's own Open-in-new-tab control may use it")

    def test_links_keep_their_href_so_they_still_work_without_js(self):
        app = Application.objects.create(
            student=self.profile, scholarship=self.scholarship, status='Approved',
            form_data={},
        )
        doc = ApplicationDocument.objects.create(
            application=app, name='Prospectus', file=_upload('pros.pdf'))
        c = Client()
        c.login(email='juan@bipsu.edu.ph', password='pw')
        r = c.get('/student/applications/')
        self.assertContains(r, f'href="{doc.file.url}"')
