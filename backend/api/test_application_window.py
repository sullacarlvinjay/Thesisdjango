from datetime import date, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from api.models import (
    Application, Scholarship, StaffProfile, StudentProfile, SystemSettings, User,
)


class WindowArithmeticTest(TestCase):
    def _programme(self, **kw):
        return Scholarship(name='Academic Scholarship', type='Academic',
                           category='application', description='x',
                           eligibility='x', requirements=[], **kw)

    def test_no_window_set_means_always_open(self):
        p = self._programme()
        self.assertIsNone(p.applications_close_on)
        self.assertTrue(p.accepts_applications_on(date(1999, 1, 1)))
        self.assertTrue(p.accepts_applications_on(date(2099, 1, 1)))
        self.assertEqual(p.window_closed_reason(date(2099, 1, 1)), '')

    def test_one_day_open_means_the_opening_day_only(self):
        p = self._programme(applications_open_on=date(2026, 9, 3),
                            applications_open_days=1)
        self.assertEqual(p.applications_close_on, date(2026, 9, 3))
        self.assertTrue(p.accepts_applications_on(date(2026, 9, 3)))
        self.assertFalse(p.accepts_applications_on(date(2026, 9, 4)))

    def test_both_ends_of_the_window_are_inclusive(self):
        p = self._programme(applications_open_on=date(2026, 9, 3),
                            applications_open_days=14)
        self.assertEqual(p.applications_close_on, date(2026, 9, 16))
        for day, open_ in ((date(2026, 9, 2), False), (date(2026, 9, 3), True),
                           (date(2026, 9, 16), True), (date(2026, 9, 17), False)):
            self.assertEqual(p.accepts_applications_on(day), open_, day)

    def test_an_opening_date_with_no_length_never_closes(self):
        p = self._programme(applications_open_on=date(2026, 9, 3))
        self.assertIsNone(p.applications_close_on)
        self.assertFalse(p.accepts_applications_on(date(2026, 9, 2)))
        self.assertTrue(p.accepts_applications_on(date(2099, 1, 1)))

    def test_the_reason_says_which_side_of_the_window_they_are_on(self):
        p = self._programme(applications_open_on=date(2026, 9, 3),
                            applications_open_days=14)
        early = p.window_closed_reason(date(2026, 9, 1))
        late = p.window_closed_reason(date(2026, 10, 1))
        self.assertIn('open on September 03, 2026', early)
        self.assertIn('closed on September 16, 2026', late)


class ApplyFormRespectsTheWindowTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        for name, stype in (('Academic Scholarship', 'Academic'),
                            ('Tertiary Education Subsidy', 'TES'),
                            ('BiPSU Staff Scholarship', 'Staff')):
            Scholarship.objects.create(
                name=name, type=stype, category='application',
                description='x', eligibility='x', requirements=[])

        su = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            first_name='Juan', last_name='Cruz', role='student')
        StudentProfile.objects.create(
            user=su, student_id='2024-0001', course='BSCS', year_level=2)
        self.student = Client()
        self.assertTrue(self.student.login(email='s@bipsu.edu.ph', password='pw'))

        tu = User.objects.create_user(
            username='t@bipsu.edu.ph', email='t@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Reyes', role='nsu_staff')
        StaffProfile.objects.create(user=tu)
        self.staff = Client()
        self.assertTrue(self.staff.login(email='t@bipsu.edu.ph', password='pw'))

    def _window(self, stype, opens, days=None):
        Scholarship.objects.filter(type=stype).update(
            applications_open_on=opens, applications_open_days=days)

    def _shut(self, stype, when='future'):
        today = timezone.localdate()
        if when == 'future':
            self._window(stype, today + timedelta(days=7), 14)
        else:
            self._window(stype, today - timedelta(days=30), 7)

    def test_a_programme_with_no_window_is_open(self):
        for client, url in ((self.student, '/student/apply/academic/'),
                            (self.staff, '/nsu-staff/apply/')):
            r = client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertFalse(r.context.get('blocked'), url)

    def test_a_programme_inside_its_window_is_open(self):
        today = timezone.localdate()
        for stype in ('Academic', 'Staff'):
            self._window(stype, today - timedelta(days=1), 5)
        for client, url in ((self.student, '/student/apply/academic/'),
                            (self.staff, '/nsu-staff/apply/')):
            self.assertFalse(client.get(url).context.get('blocked'), url)

    def test_the_academic_form_closes_outside_its_window(self):
        self._shut('Academic')
        r = self.student.get('/student/apply/academic/')
        self.assertTrue(r.context['blocked'])
        self.assertIn('open on', r.context['blocked_reason'])

    def test_a_window_already_past_reads_as_closed_rather_than_upcoming(self):
        self._shut('Academic', 'past')
        r = self.student.get('/student/apply/academic/')
        self.assertTrue(r.context['blocked'])
        self.assertIn('closed on', r.context['blocked_reason'])

    def test_the_staff_form_closes_outside_its_window(self):
        self._shut('Staff')
        r = self.staff.get('/nsu-staff/apply/')
        self.assertTrue(r.context['blocked'])
        self.assertIn('open on', r.context['blocked_reason'])

    def test_one_programmes_window_does_not_shut_another(self):
        self._shut('Academic')
        self.assertTrue(self.student.get('/student/apply/academic/').context['blocked'])
        self.assertFalse(self.staff.get('/nsu-staff/apply/').context.get('blocked'))

    def test_a_closed_window_refuses_the_post_too(self):
        from api.models import Application
        self._shut('Academic')
        self.student.post('/student/apply/academic/', {'gwa': '1.20'})
        self.assertFalse(Application.objects.exists())


class SwitchClosesTheFormOutrightTest(TestCase):
    def _programme(self, **kw):
        return Scholarship(name='Academic Scholarship', type='Academic',
                           category='application', description='x',
                           eligibility='x', requirements=[], **kw)

    def test_off_closes_a_programme_with_no_window_at_all(self):
        p = self._programme(accepting_applications=False)
        self.assertFalse(p.accepts_applications_on(date(2026, 9, 3)))
        self.assertEqual(p.window_closed_reason(date(2026, 9, 3)),
                         'Applications for the Academic Scholarship are closed.')

    def test_off_beats_a_window_that_is_open_today(self):
        p = self._programme(accepting_applications=False,
                            applications_open_on=date(2026, 9, 3),
                            applications_open_days=14)
        self.assertFalse(p.accepts_applications_on(date(2026, 9, 4)))
        self.assertIn('are closed', p.window_closed_reason(date(2026, 9, 4)))

    def test_the_closed_reason_names_no_date_it_cannot_stand_behind(self):
        reason = self._programme(accepting_applications=False).window_closed_reason(
            date(2026, 9, 3))
        self.assertNotIn('open on', reason)
        self.assertNotIn('closed on', reason)

    def test_on_is_the_default_so_nothing_shuts_on_migrate(self):
        p = self._programme()
        self.assertTrue(p.accepting_applications)
        self.assertTrue(p.accepting_renewals)
        self.assertTrue(p.accepts_applications_on(date(2026, 9, 3)))
        self.assertTrue(p.accepts_renewals_on(date(2026, 9, 3)))


class RenewalsHaveTheirOwnWindowTest(TestCase):
    def _programme(self, **kw):
        return Scholarship(name='Academic Scholarship', type='Academic',
                           category='application', description='x',
                           eligibility='x', requirements=[], **kw)

    def test_the_renewal_window_does_the_same_arithmetic(self):
        p = self._programme(renewals_open_on=date(2026, 9, 3),
                            renewals_open_days=14)
        self.assertEqual(p.renewals_close_on, date(2026, 9, 16))
        for day, open_ in ((date(2026, 9, 2), False), (date(2026, 9, 3), True),
                           (date(2026, 9, 16), True), (date(2026, 9, 17), False)):
            self.assertEqual(p.accepts_renewals_on(day), open_, day)

    def test_closing_applications_leaves_renewals_open(self):
        p = self._programme(accepting_applications=False)
        self.assertFalse(p.accepts_applications_on(date(2026, 9, 3)))
        self.assertTrue(p.accepts_renewals_on(date(2026, 9, 3)))

    def test_closing_renewals_leaves_applications_open(self):
        p = self._programme(accepting_renewals=False)
        self.assertTrue(p.accepts_applications_on(date(2026, 9, 3)))
        self.assertFalse(p.accepts_renewals_on(date(2026, 9, 3)))

    def test_the_reason_says_renewals_rather_than_applications(self):
        p = self._programme(renewals_open_on=date(2026, 9, 3),
                            renewals_open_days=14)
        self.assertIn('Renewals for the Academic Scholarship',
                      p.renewal_closed_reason(date(2026, 9, 1)))


class RenewalFormRespectsItsWindowTest(TestCase):
    URL = '/student/renewal/academic/'

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        academic = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        su = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            first_name='Juan', last_name='Cruz', role='student')
        profile = StudentProfile.objects.create(
            user=su, student_id='2024-0001', course='BSCS', year_level=2)
        Application.objects.create(
            student=profile, scholarship=academic, status='Approved',
            school_year='2026-2027', semester='1st Semester')
        self.student = Client()
        self.assertTrue(self.student.login(email='s@bipsu.edu.ph', password='pw'))

    def test_a_programme_with_no_renewal_window_is_open(self):
        r = self.student.get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context.get('blocked'))

    def test_the_switch_closes_the_renewal_form(self):
        Scholarship.objects.filter(type='Academic').update(accepting_renewals=False)
        r = self.student.get(self.URL)
        self.assertTrue(r.context['blocked'])
        self.assertIn('Renewals', r.context['blocked_reason'])

    def test_a_window_still_ahead_closes_it_with_the_date(self):
        Scholarship.objects.filter(type='Academic').update(
            renewals_open_on=timezone.localdate() + timedelta(days=7),
            renewals_open_days=14)
        r = self.student.get(self.URL)
        self.assertTrue(r.context['blocked'])
        self.assertIn('open on', r.context['blocked_reason'])

    def test_a_closed_window_refuses_the_post_too(self):
        from api.models import AcademicRenewal
        Scholarship.objects.filter(type='Academic').update(accepting_renewals=False)
        self.student.post(self.URL, {})
        self.assertFalse(AcademicRenewal.objects.exists())

    def test_closing_applications_does_not_close_the_renewal_form(self):
        Scholarship.objects.filter(type='Academic').update(
            accepting_applications=False)
        self.assertFalse(self.student.get(self.URL).context.get('blocked'))


class WindowIsSetOnTheQueueItGovernsTest(TestCase):
    APPLICATIONS = '/vpsea/affirmative/'
    RENEWALS = '/vpsea/renewals/'

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))
        self.s = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        self.staff = Scholarship.objects.create(
            name='BiPSU Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[])

    def _applications(self, tab='academic', **extra):
        data = {'window': 'applications', 'tab': tab,
                'accepting_applications': 'on'}
        data.update(extra)
        return self.c.post(self.APPLICATIONS, data)

    def _renewals(self, **extra):
        data = {'window': 'renewals', 'accepting_renewals': 'on'}
        data.update(extra)
        return self.c.post(self.RENEWALS, data)

    def test_the_applications_tab_offers_the_application_window(self):
        r = self.c.get(self.APPLICATIONS)
        self.assertContains(r, 'name="applications_open_on"')
        self.assertContains(r, 'name="applications_open_days"')
        self.assertContains(r, 'name="accepting_applications"')

    def test_the_renewals_tab_offers_the_renewal_window(self):
        r = self.c.get(self.RENEWALS)
        self.assertContains(r, 'name="renewals_open_on"')
        self.assertContains(r, 'name="renewals_open_days"')
        self.assertContains(r, 'name="accepting_renewals"')

    def test_neither_is_on_the_programme_form_any_more(self):
        r = self.c.get(f'/vpsea/scholarships/{self.s.pk}/edit/')
        self.assertNotContains(r, 'name="applications_open_on"')
        self.assertNotContains(r, 'name="renewals_open_on"')

    def test_editing_a_programme_leaves_its_windows_alone(self):
        Scholarship.objects.filter(pk=self.s.pk).update(
            applications_open_on=date(2026, 9, 3), applications_open_days=14,
            accepting_renewals=False)
        self.c.post(f'/vpsea/scholarships/{self.s.pk}/edit/', {
            'name': 'Academic Scholarship', 'type': 'Academic',
            'description': 'corrected', 'group': 'internal'})
        self.s.refresh_from_db()
        self.assertEqual(self.s.applications_open_on, date(2026, 9, 3))
        self.assertEqual(self.s.applications_open_days, 14)
        self.assertFalse(self.s.accepting_renewals)

    def test_the_office_sets_an_application_window(self):
        self._applications(applications_open_on='2026-09-03',
                           applications_open_days='14')
        self.s.refresh_from_db()
        self.assertEqual(self.s.applications_close_on, date(2026, 9, 16))

    def test_the_office_sets_a_renewal_window(self):
        self._renewals(renewals_open_on='2026-09-03', renewals_open_days='14')
        self.s.refresh_from_db()
        self.assertEqual(self.s.renewals_close_on, date(2026, 9, 16))

    def test_unticking_the_switch_closes_the_form(self):
        self.c.post(self.APPLICATIONS, {'window': 'applications', 'tab': 'academic'})
        self.s.refresh_from_db()
        self.assertFalse(self.s.accepting_applications)
        self.assertFalse(self.s.accepts_applications_on(timezone.localdate()))

    def test_ticking_it_again_reopens_the_form(self):
        Scholarship.objects.filter(pk=self.s.pk).update(accepting_applications=False)
        self._applications()
        self.s.refresh_from_db()
        self.assertTrue(self.s.accepts_applications_on(timezone.localdate()))

    def test_clearing_both_boxes_leaves_it_open_with_no_end(self):
        Scholarship.objects.filter(pk=self.s.pk).update(
            applications_open_on=date(2026, 9, 3), applications_open_days=14)
        self._applications(applications_open_on='', applications_open_days='')
        self.s.refresh_from_db()
        self.assertIsNone(self.s.applications_open_on)
        self.assertTrue(self.s.accepts_applications_on(date(2099, 1, 1)))

    def test_the_staff_tab_sets_the_staff_programmes_window(self):
        self._applications(tab='staff', applications_open_on='2026-10-01',
                           applications_open_days='7')
        self.staff.refresh_from_db()
        self.s.refresh_from_db()
        self.assertEqual(self.staff.applications_close_on, date(2026, 10, 7))
        self.assertIsNone(self.s.applications_open_on)

    def test_a_length_with_no_opening_date_is_refused(self):
        from urllib.parse import unquote
        r = self._applications(applications_open_days='14')
        self.assertIn('needs an opening date', unquote(r['Location']))
        self.s.refresh_from_db()
        self.assertIsNone(self.s.applications_open_days)

    def test_a_length_that_is_not_a_number_is_refused(self):
        from urllib.parse import unquote
        r = self._renewals(renewals_open_on='2026-09-03',
                           renewals_open_days='two weeks')
        self.assertIn('whole number', unquote(r['Location']))
        self.s.refresh_from_db()
        self.assertIsNone(self.s.renewals_open_days)

    def test_a_zero_day_window_is_refused(self):
        from urllib.parse import unquote
        r = self._applications(applications_open_on='2026-09-03',
                               applications_open_days='0')
        self.assertIn('at least 1', unquote(r['Location']))
        self.s.refresh_from_db()
        self.assertIsNone(self.s.applications_open_days)

    def test_a_decision_post_is_not_mistaken_for_a_window_post(self):
        self.c.post(self.APPLICATIONS, {'tab': 'academic', 'app_id': '999',
                                        'status': 'Approved'})
        self.s.refresh_from_db()
        self.assertTrue(self.s.accepting_applications)
