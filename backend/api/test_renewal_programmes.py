"""A scholar who holds two awards renews each of them separately.

The renewal page was Academic's alone. It asked Academic's renewal window, wrote
an `AcademicRenewal` carrying nothing that said which programme it was for, and
the office approved every one of them into an Academic award. That is three
separate failures for a student holding two scholarships, which is an ordinary
thing to hold here — two declared at registration and both approved is how it
usually happens:

* They could not renew the second award at all.
* Both renewals reached the office as identical rows.
* Approving a DOST scholar's renewal silently awarded them Academic.

So the submission now says which programme it renews. The rules that follow from
that are what this file checks, and each is a way it could go wrong again:

* **A student on one award is never asked.** A question with one possible answer
  is not a question; the view fills it in.
* **Only programmes whose renewal window is open are offered.** Offering a shut
  one earns the student a refusal for choosing what they were shown.
* **One closed window is not a closed page.** A scholar on two awards whose
  Academic renewals have closed can still renew the other one.
* **A replacement stays inside its own programme.** Re-uploading for the second
  award must not overwrite the first one's documents.
"""
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    AcademicRenewal, Application, Scholarship, ScholarshipLinkRequest,
    StudentProfile, SystemSettings, User,
)


def a_document(name='cog.pdf'):
    return SimpleUploadedFile(name, b'x' * 512, content_type='application/pdf')


def documents():
    return {'certificate_of_grades': a_document('cog.pdf'),
            'certificate_of_enrollment': a_document('coe.pdf')}


class RenewalPageTest(TestCase):
    """One student, and whatever awards each test decides to give them."""

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.academic = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        self.dost = Scholarship.objects.create(
            name='DOST Scholarship', type='DOST', category='recommendation',
            group='external', description='x', eligibility='x', requirements=[])
        user = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Reyes', role='student')
        self.profile = StudentProfile.objects.create(user=user, student_id='23-0001')
        self.c = Client()
        self.assertTrue(self.c.login(email='s@bipsu.edu.ph', password='pw'))

    # ── fixtures ────────────────────────────────────────────────────────────

    def _award(self, scholarship):
        Application.objects.create(
            student=self.profile, scholarship=scholarship, status='Approved',
            school_year='2026-2027', semester='1st Semester')

    def _close_renewals(self, scholarship):
        """Shut one programme's renewal window, and only that one's."""
        scholarship.renewals_open_on = date.today() + timedelta(days=30)
        scholarship.renewals_open_days = 14
        scholarship.save()

    def _page(self):
        return self.c.get('/student/renewal/academic/')

    def _submit(self, **extra):
        data = documents()
        data.update(extra)
        return self.c.post('/student/renewal/academic/', data)

    # ── holding nothing ─────────────────────────────────────────────────────

    def test_a_student_holding_nothing_is_told_so_rather_than_shown_a_form(self):
        page = self._page()
        self.assertContains(page, 'Nothing to renew yet')
        self.assertNotContains(page, 'Submit Renewal Documents')

    def test_and_a_submission_from_one_writes_no_renewal(self):
        self._submit(scholarship_type='Academic')
        self.assertEqual(AcademicRenewal.objects.count(), 0)

    # ── holding one ─────────────────────────────────────────────────────────

    def test_one_award_is_not_a_question_worth_asking(self):
        self._award(self.academic)
        page = self._page()
        self.assertNotContains(page, 'Which scholarship are you renewing?')
        self.assertContains(page, 'name="scholarship_type" value="Academic"')

    def test_and_the_renewal_is_filed_against_it_without_being_told(self):
        self._award(self.academic)
        self._submit()
        renewal = AcademicRenewal.objects.get()
        self.assertEqual(renewal.scholarship_type, 'Academic')

    def test_the_programme_is_read_off_the_award_not_off_the_page_name(self):
        """The page is /renewal/academic/ for historical reasons. A DOST scholar
        renewing there is renewing DOST."""
        self._award(self.dost)
        self._submit()
        self.assertEqual(AcademicRenewal.objects.get().scholarship_type, 'DOST')

    # ── holding two ─────────────────────────────────────────────────────────

    def test_two_awards_are_both_offered(self):
        self._award(self.academic)
        self._award(self.dost)
        page = self._page()
        self.assertContains(page, 'Which scholarship are you renewing?')
        self.assertContains(page, '<option value="Academic">')
        self.assertContains(page, '<option value="DOST">')

    def test_each_one_is_renewed_on_its_own(self):
        self._award(self.academic)
        self._award(self.dost)
        self._submit(scholarship_type='Academic')
        self._submit(scholarship_type='DOST')
        self.assertEqual(
            sorted(AcademicRenewal.objects.values_list('scholarship_type', flat=True)),
            ['Academic', 'DOST'])

    def test_choosing_nothing_is_refused_rather_than_guessed(self):
        self._award(self.academic)
        self._award(self.dost)
        page = self._submit()
        self.assertContains(page, 'Choose which scholarship you are renewing.')
        self.assertEqual(AcademicRenewal.objects.count(), 0)

    def test_a_programme_they_do_not_hold_is_refused(self):
        self._award(self.academic)
        self._award(self.dost)
        page = self._submit(scholarship_type='CHED')
        self.assertContains(page, 'not a programme you hold')
        self.assertEqual(AcademicRenewal.objects.count(), 0)

    def test_an_approved_link_counts_as_an_award_to_renew(self):
        """Two records make somebody a scholar and only one is an Application."""
        self._award(self.academic)
        ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='CHED', status='Approved',
            term_label='26-1')
        self.assertContains(self._page(), '<option value="CHED">')

    # ── replacing what is already in ────────────────────────────────────────

    def test_re_uploading_replaces_that_programmes_documents(self):
        self._award(self.academic)
        self._submit()
        self._submit()
        self.assertEqual(AcademicRenewal.objects.count(), 1)

    def test_and_leaves_the_other_programmes_alone(self):
        """The failure this guards: a scholar renewing their second award
        overwriting the first one's documents instead of adding to them."""
        self._award(self.academic)
        self._award(self.dost)
        self._submit(scholarship_type='Academic')
        self._submit(scholarship_type='DOST')
        self._submit(scholarship_type='DOST')
        self.assertEqual(AcademicRenewal.objects.count(), 2)
        self.assertEqual(
            AcademicRenewal.objects.filter(scholarship_type='Academic').count(), 1)

    # ── windows ─────────────────────────────────────────────────────────────

    def test_a_shut_programme_is_not_offered(self):
        """With one of the two shut there is only one answer left, so the form
        stops asking and fills it in — the same as a student on one award."""
        self._award(self.academic)
        self._award(self.dost)
        self._close_renewals(self.academic)
        page = self._page()
        self.assertNotContains(page, '<option value="Academic">')
        self.assertContains(page, 'name="scholarship_type" value="DOST"')

    def test_one_shut_window_out_of_two_is_not_a_shut_page(self):
        self._award(self.academic)
        self._award(self.dost)
        self._close_renewals(self.academic)
        page = self._page()
        self.assertNotContains(page, 'Renewals Are Closed')
        self.assertContains(page, 'Academic Scholarship — renewals closed')

    def test_a_shut_programme_cannot_be_posted_past_the_form(self):
        self._award(self.academic)
        self._award(self.dost)
        self._close_renewals(self.academic)
        self._submit(scholarship_type='Academic')
        self.assertEqual(AcademicRenewal.objects.count(), 0)

    def test_every_window_shut_does_close_the_page(self):
        self._award(self.academic)
        self._close_renewals(self.academic)
        self.assertContains(self._page(), 'Renewals Are Closed')

    # ── documents are still required ────────────────────────────────────────

    def test_the_two_certificates_are_still_required(self):
        self._award(self.academic)
        page = self.c.post('/student/renewal/academic/', {})
        self.assertContains(page, 'Certificate of Grades is required.')
        self.assertContains(page, 'Certificate of Enrollment is required.')
        self.assertEqual(AcademicRenewal.objects.count(), 0)


class TheOfficeSeesWhichProgrammeTest(TestCase):
    """The other half of it: approving the right award, and being able to tell
    two of a scholar's renewals apart on screen."""

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.academic = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        self.dost = Scholarship.objects.create(
            name='DOST Scholarship', type='DOST', category='recommendation',
            group='external', description='x', eligibility='x', requirements=[])
        student = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Reyes', role='student')
        self.profile = StudentProfile.objects.create(user=student, student_id='23-0001')
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def _renewal(self, stype):
        return AcademicRenewal.objects.create(
            student=self.profile, scholarship_type=stype,
            certificate_of_grades=a_document(), certificate_of_enrollment=a_document())

    def test_the_table_names_the_programme(self):
        self._renewal('DOST')
        self.assertContains(self.c.get('/vpsea/renewals/'), 'DOST')

    def test_approving_a_dost_renewal_awards_dost(self):
        """It awarded Academic to everybody, whatever they were renewing."""
        renewal = self._renewal('DOST')
        self.c.post('/vpsea/renewals/',
                    {'renewal_id': renewal.id, 'status': 'Approved', 'remarks': ''})
        award = Application.objects.get(student=self.profile)
        self.assertEqual(award.scholarship, self.dost)

    def test_approving_an_academic_renewal_still_awards_academic(self):
        renewal = self._renewal('Academic')
        self.c.post('/vpsea/renewals/',
                    {'renewal_id': renewal.id, 'status': 'Approved', 'remarks': ''})
        award = Application.objects.get(student=self.profile)
        self.assertEqual(award.scholarship, self.academic)

    def test_a_programme_with_no_catalogue_row_writes_no_award(self):
        """Rather than falling back to whichever programme happens to be first."""
        renewal = self._renewal('CHED')
        self.c.post('/vpsea/renewals/',
                    {'renewal_id': renewal.id, 'status': 'Approved', 'remarks': ''})
        self.assertFalse(Application.objects.filter(student=self.profile).exists())

    def test_the_notification_says_which_renewal_was_decided(self):
        from api.models import Notification

        renewal = self._renewal('DOST')
        self.c.post('/vpsea/renewals/',
                    {'renewal_id': renewal.id, 'status': 'Approved', 'remarks': ''})
        note = Notification.objects.filter(student=self.profile).first()
        self.assertIsNotNone(note)
        self.assertIn('DOST', note.title + note.body)
