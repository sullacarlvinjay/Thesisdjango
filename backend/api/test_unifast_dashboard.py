"""The UniFAST dashboard reports real records, not placeholder figures."""
from django.test import Client, TestCase

from api import tes_report
from api.models import (
    Announcement, Application, ImportedScholar, Scholarship, StudentProfile,
    SystemSettings, TESApplication, User,
)


class UniFASTDashboardTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        for stype in ('TES', 'TDP'):
            Scholarship.objects.create(
                name=stype, type=stype, category='application',
                description='x', eligibility='x', requirements=[],
            )
        self.unifast = User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
            password='pw', role='unifast',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='unifast@bipsu.edu.ph', password='pw'))

    def _profile(self, last, sid):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph', password='pw',
            first_name='Test', last_name=last, role='student',
        )
        return StudentProfile.objects.create(
            user=u, student_id=sid, course='BSCS', year_level=2)

    def _tes(self, last, sid, status='Pending'):
        return TESApplication.objects.create(student=self._profile(last, sid), status=status)

    def _tdp(self, last, sid):
        return Application.objects.create(
            student=self._profile(last, sid),
            scholarship=Scholarship.objects.get(type='TDP'),
            status='Approved', form_data={},
        )

    def test_counts_come_from_the_records(self):
        self._tes('Cruz', '2024-0001', 'Approved')
        self._tes('Reyes', '2024-0002', 'Approved')
        self._tes('Lim', '2024-0003', 'Pending')
        self._tes('Diaz', '2024-0004', 'Rejected')
        self._tdp('Bautista', '2024-0005')

        r = self.c.get('/unifast/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['tes_total'], 4)
        self.assertEqual(r.context['tes_beneficiaries'], 2)
        self.assertEqual(r.context['tes_pending_count'], 1)
        self.assertEqual(r.context['tes_rejected'], 1)
        self.assertEqual(r.context['tdp_scholars'], 1)
        self.assertEqual(r.context['total_scholars'], 3)

    def test_approval_rate_ignores_applications_still_pending(self):
        self._tes('Cruz', '2024-0001', 'Approved')
        self._tes('Reyes', '2024-0002', 'Approved')
        self._tes('Diaz', '2024-0003', 'Rejected')
        self._tes('Lim', '2024-0004', 'Pending')
        r = self.c.get('/unifast/')
        # 2 approved of 3 decided — the pending one is not counted yet.
        self.assertEqual(r.context['approval_rate'], 67)

    def test_approval_rate_is_zero_when_nothing_is_reviewed_yet(self):
        self._tes('Lim', '2024-0001', 'Pending')
        r = self.c.get('/unifast/')
        self.assertEqual(r.context['approval_rate'], 0)

    def test_no_billing_figure_is_derived(self):
        """CHED sets what a grantee is paid, so the dashboard does not compute
        a billing total from a rate this office does not decide."""
        self._tes('Cruz', '2024-0001', 'Approved')
        self._tes('Reyes', '2024-0002', 'Approved')
        r = self.c.get('/unifast/')
        self.assertNotIn('tes_billing', r.context)
        self.assertNotIn('tes_rate', r.context)
        # The grantee count is still reported — that one is ours to know.
        self.assertEqual(r.context['tes_beneficiaries'], 2)

    def test_review_queue_shows_the_longest_waiting_first(self):
        self._tes('Cruz', '2024-0001', 'Pending')
        self._tes('Reyes', '2024-0002', 'Pending')
        self._tes('Diaz', '2024-0003', 'Approved')

        r = self.c.get('/unifast/')
        queue = r.context['pending_queue']
        self.assertEqual([a.student.user.last_name for a in queue], ['Cruz', 'Reyes'])
        self.assertContains(r, 'awaiting review')
        self.assertContains(r, '2024-0001')

    def test_empty_queue_says_so_instead_of_showing_a_blank_table(self):
        r = self.c.get('/unifast/')
        self.assertEqual(r.context['pending_queue'], [])
        self.assertContains(r, 'Nothing waiting')

    def test_unclaimed_imported_rows_are_surfaced_per_programme(self):
        ImportedScholar.objects.create(scholarship_type='TDP', term_label='26-1',
                                     last_name='Cruz', first_name='Ana')
        ImportedScholar.objects.create(scholarship_type='TES', term_label='26-1',
                                     last_name='Lim', first_name='Leo')
        claimed = ImportedScholar.objects.create(
            scholarship_type='TES', term_label='26-1',
            last_name='Diaz', first_name='Dan', claimed_by=self._profile('Diaz', '2024-0009'))
        self.assertIsNotNone(claimed.claimed_by)

        r = self.c.get('/unifast/')
        self.assertEqual(r.context['imported'], {'TDP': 1, 'TES': 1})
        self.assertEqual(r.context['imported_total'], 2)

    def test_imported_rows_from_other_semesters_are_not_counted(self):
        ImportedScholar.objects.create(scholarship_type='TDP', term_label='25-2',
                                     last_name='Old', first_name='Row')
        r = self.c.get('/unifast/')
        self.assertEqual(r.context['imported']['TDP'], 0)

    def test_only_the_offices_own_announcements_are_listed(self):
        vpsea = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw', role='vpsea')
        Announcement.objects.create(title='Ours', body='b', published_by=self.unifast)
        Announcement.objects.create(title='Theirs', body='b', published_by=vpsea)
        r = self.c.get('/unifast/')
        self.assertEqual([a.title for a in r.context['announcements']], ['Ours'])

    def test_the_period_shown_follows_system_settings(self):
        r = self.c.get('/unifast/')
        self.assertEqual(r.context['academic_year'], '2026-2027')
        self.assertEqual(r.context['semester'], '1st Semester')
        self.assertContains(r, '2026-2027')

    def test_no_invented_figures_remain(self):
        r = self.c.get('/unifast/')
        body = r.content.decode()
        for placeholder in ('3.45M', 'billing_approved_pct', '92%'):
            self.assertNotIn(placeholder, body, f'{placeholder} is a made-up figure')

    def test_dashboard_is_closed_to_other_roles(self):
        other = Client()
        User.objects.create_user(
            username='v2@bipsu.edu.ph', email='v2@bipsu.edu.ph', password='pw', role='vpsea')
        other.login(email='v2@bipsu.edu.ph', password='pw')
        r = other.get('/unifast/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])
