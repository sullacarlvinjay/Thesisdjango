from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from api.models import (
    ApplicantRecord, Scholarship, StaffRenewal, StudentProfile, SystemSettings,
    User,
)

REAL_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'closed-window-tests',
    },
}

THIS_TERM = {'term_label': '26-1', 'school_year': '2026-2027',
             'semester': '1st Semester'}


@override_settings(CACHES=REAL_CACHE)
class StaffRenewalIsGuardedTest(TestCase):
    """Filing a renewal must behave like the student one.

    It did not. The page listed every renewal the employee had ever filed,
    a POST created a new row unconditionally — so each resubmission added
    another — and nothing consulted the renewal window at all.
    """

    def setUp(self):
        cache.clear()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        self.programme = Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
            accepting_applications=True, accepting_renewals=True)
        self.user = User.objects.create_user(
            username='rosa@bipsu.edu.ph', email='rosa@bipsu.edu.ph',
            password='pw', first_name='Rosa', last_name='Delgado',
            role='nsu_staff')
        ApplicantRecord.objects.create(
            full_name='Rosa Delgado', email='rosa@bipsu.edu.ph',
            qualified_for='Staff', status='Approved', course='—', year_level=1,
            is_nsu_staff=True, **THIS_TERM)
        self.c = Client()
        self.assertTrue(self.c.login(email='rosa@bipsu.edu.ph', password='pw'))

    def _file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.c.post('/nsu-staff/renewal/', {
            'supporting_document': SimpleUploadedFile(
                'grades.pdf', b'%PDF-1.4 x', content_type='application/pdf')})

    def test_filing_twice_does_not_leave_two_renewals(self):
        self._file()
        self._file()
        self.assertEqual(
            StaffRenewal.objects.filter(staff_user=self.user).count(), 1,
            'each resubmission added another row, so the page filled up with '
            'history nobody filed')

    def test_a_renewal_without_a_document_is_refused(self):
        r = self.c.post('/nsu-staff/renewal/', {})
        self.assertEqual(StaffRenewal.objects.count(), 0)
        self.assertContains(r, 'supporting document is required')

    def test_last_terms_renewal_is_not_listed_this_term(self):
        StaffRenewal.objects.create(
            staff_user=self.user, term_label='25-2',
            school_year='2025-2026', semester='2nd Semester')
        listed = self.c.get('/nsu-staff/renewal/').context['renewals']
        self.assertEqual(
            [r.term_label for r in listed], [],
            "last term's renewal is still on this term's page")

    def test_a_closed_window_refuses_and_says_why(self):
        self.programme.accepting_renewals = False
        self.programme.save()
        cache.clear()
        r = self._file()
        self.assertEqual(
            StaffRenewal.objects.count(), 0,
            'a renewal was filed while renewals were closed')
        self.assertTrue(r.context['blocked'])
        self.assertTrue(r.context['blocked_reason'])


@override_settings(CACHES=REAL_CACHE)
class ClosedWindowsAreNotOfferedTest(TestCase):
    """A tab that only leads to a refusal should not be offered.

    Hiding it is only half the job — a reader who remembers the tab needs to
    be told where it went, so the notice carries the office's own wording
    about when the window reopens.
    """

    def setUp(self):
        cache.clear()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        self.programme = Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
            accepting_applications=True, accepting_renewals=True)
        User.objects.create_user(
            username='rosa@bipsu.edu.ph', email='rosa@bipsu.edu.ph',
            password='pw', first_name='Rosa', last_name='Delgado',
            role='nsu_staff')
        self.c = Client()
        self.assertTrue(self.c.login(email='rosa@bipsu.edu.ph', password='pw'))

    def _dashboard(self):
        cache.clear()
        return self.c.get('/nsu-staff/')

    def test_the_apply_tab_shows_while_applications_are_open(self):
        self.assertContains(self._dashboard(), '/nsu-staff/apply/')

    def test_the_apply_tab_goes_when_applications_close(self):
        self.programme.accepting_applications = False
        self.programme.save()
        self.assertNotContains(self._dashboard(), '/nsu-staff/apply/')

    def test_the_renewal_tab_goes_when_renewals_close(self):
        self.programme.accepting_renewals = False
        self.programme.save()
        self.assertNotContains(self._dashboard(), '/nsu-staff/renewal/')

    def test_closing_a_window_says_so_rather_than_only_hiding_the_tab(self):
        self.programme.accepting_applications = False
        self.programme.save()
        r = self._dashboard()
        self.assertContains(r, 'Applications are closed')
        self.assertContains(
            r, r.context['applications_closed_reason'],
            msg_prefix='the notice does not carry the reason, so the reader '
                       'is told a tab vanished but not when it returns')

    def test_nothing_is_said_while_both_windows_are_open(self):
        self.assertNotContains(self._dashboard(), 'are closed.')


@override_settings(CACHES=REAL_CACHE)
class StudentClosedWindowsTest(TestCase):
    """The same rule on the student side."""

    def setUp(self):
        cache.clear()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        self.programme = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic',
            category='application', description='x', eligibility='x',
            requirements=[], accepting_applications=True,
            accepting_renewals=True)
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', first_name='Ana', last_name='Lim', role='student',
            verification_status='approved')
        StudentProfile.objects.create(
            user=user, student_id='2022-00111', course='BSCS', year_level=2)
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def _page(self):
        cache.clear()
        return self.c.get('/student/applications/')

    def test_the_apply_tab_shows_while_applications_are_open(self):
        self.assertContains(self._page(), '/student/apply/academic/')

    def test_the_apply_tab_goes_when_applications_close(self):
        self.programme.accepting_applications = False
        self.programme.save()
        r = self._page()
        self.assertNotContains(r, '/student/apply/academic/')
        self.assertContains(r, 'Applications are closed')
