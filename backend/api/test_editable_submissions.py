from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.constants import APPLICATION_STATUSES, EDITABLE_APPLICATION_STATUSES
from api.models import (
    AcademicRenewal, Application, Scholarship, StudentProfile, SystemSettings,
    User,
)


def a_pdf(name='doc.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


class StudentMixin:
    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        self.scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student')
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS', year_level=3,
            gwa=1.25, gender='Female', date_of_birth='2004-03-11',
            contact_number='09171234567', barangay='Brgy. Larrazabal',
            municipality='Naval', province='Biliran',
            mother_last_name='Lim', mother_first_name='Rosa')
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def apply(self, **extra):
        from api.test_academic_application import a_complete_application

        data = a_complete_application(gwa='1.25')
        data['doc_certificate_of_grades'] = a_pdf('cog.pdf')
        data.update(extra)
        return self.c.post('/student/apply/academic/', data)


class DraftIsGoneTest(TestCase):
    def test_draft_is_not_a_status_any_more(self):
        self.assertNotIn('Draft', [key for key, _ in APPLICATION_STATUSES])

    def test_the_statuses_a_student_may_still_edit_are_the_undecided_ones(self):
        self.assertEqual(set(EDITABLE_APPLICATION_STATUSES),
                         {'Pending Validation', 'Needs Revision'})


class EditAnApplicationTest(StudentMixin, TestCase):

    def test_applying_creates_one_application(self):
        self.apply()
        self.assertEqual(Application.objects.filter(student=self.profile).count(), 1)

    def test_applying_again_while_pending_edits_it_rather_than_making_a_second(self):
        self.apply()
        self.apply(gwa='1.10')
        apps = Application.objects.filter(student=self.profile)
        self.assertEqual(apps.count(), 1, 'a correction is not a second application')
        self.assertEqual(apps.first().form_data['gwa'], '1.10')

    def test_the_form_comes_back_filled_in_rather_than_blocked(self):
        self.apply()
        html = self.c.get('/student/apply/academic/').content.decode()
        self.assertIn('Update Application', html)
        self.assertNotIn('You cannot apply to another scholarship', html)

    def test_a_needs_revision_application_can_be_corrected_and_goes_back_in_the_queue(self):
        self.apply()
        app = Application.objects.get(student=self.profile)
        app.status = 'Needs Revision'
        app.remarks = 'Certificate of Grades is for the wrong semester.'
        app.save(update_fields=['status', 'remarks'])

        html = self.c.get('/student/apply/academic/').content.decode()
        self.assertIn('wrong semester', html, 'the student is told what to fix')

        self.apply()
        app.refresh_from_db()
        self.assertEqual(app.status, 'Pending Validation')
        self.assertEqual(app.remarks, '', 'the remark that asked for it is answered')

    def test_re_uploading_a_document_replaces_it_rather_than_adding_a_copy(self):
        self.apply()
        app = Application.objects.get(student=self.profile)
        self.assertEqual(app.documents.filter(name='Certificate Of Grades').count(), 1)
        self.apply(doc_certificate_of_grades=a_pdf('corrected.pdf'))
        self.assertEqual(app.documents.filter(name='Certificate Of Grades').count(), 1)
        self.assertIn('corrected', app.documents.get(name='Certificate Of Grades').file.name)

    def test_an_approved_application_is_final_and_closes_the_form(self):
        self.apply()
        app = Application.objects.get(student=self.profile)
        app.status = 'Approved'
        app.save(update_fields=['status'])
        html = self.c.get('/student/apply/academic/').content.decode()
        self.assertIn('There is nothing to apply for', html)
        self.assertNotIn('Update Application', html)

    def test_an_approved_application_cannot_be_edited_by_posting_anyway(self):
        self.apply()
        app = Application.objects.get(student=self.profile)
        app.status = 'Approved'
        app.form_data = {'gwa': '1.25'}
        app.save(update_fields=['status', 'form_data'])
        self.apply(gwa='1.00')
        app.refresh_from_db()
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.form_data['gwa'], '1.25')
        self.assertEqual(Application.objects.filter(student=self.profile).count(), 1)


class EditARenewalTest(StudentMixin, TestCase):

    def setUp(self):
        super().setUp()
        Application.objects.create(
            student=self.profile, scholarship=self.scholarship, status='Approved',
            school_year='2026-2027', semester='1st Semester')

    def renew(self, cog='cog.pdf', coe='coe.pdf'):
        return self.c.post('/student/renewal/academic/', {
            'certificate_of_grades': a_pdf(cog),
            'certificate_of_enrollment': a_pdf(coe),
        })

    def test_renewing_twice_while_pending_replaces_the_documents(self):
        self.renew()
        self.renew(cog='corrected.pdf')
        renewals = AcademicRenewal.objects.filter(student=self.profile)
        self.assertEqual(renewals.count(), 1, 'the office should not get two to reconcile')
        self.assertIn('corrected', renewals.first().certificate_of_grades.name)

    def test_a_decided_renewal_is_left_alone_and_a_new_one_is_taken(self):
        self.renew()
        decided = AcademicRenewal.objects.get(student=self.profile)
        decided.status = 'Rejected'
        decided.save(update_fields=['status'])
        self.renew(cog='second-try.pdf')
        self.assertEqual(AcademicRenewal.objects.filter(student=self.profile).count(), 2)
        decided.refresh_from_db()
        self.assertEqual(decided.status, 'Rejected')

    def test_the_page_says_it_is_replacing_rather_than_submitting(self):
        self.renew()
        html = self.c.get('/student/renewal/academic/').content.decode()
        self.assertIn('Replace Documents', html)
