"""TES belongs to UniFAST. VPSEA must not read or decide those applications."""
from django.test import Client, TestCase

from api.models import (
    Application, Scholarship, StudentProfile, SystemSettings, TESApplication, User,
)


class VPSEACannotTouchTESTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        for stype in ('Academic', 'TES', 'TDP'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype, category='application',
                description='x', eligibility='x', requirements=[],
            )
        self.vpsea = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))

    def _profile(self, last, sid):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph', password='pw',
            first_name='Test', last_name=last, role='student',
        )
        return StudentProfile.objects.create(
            user=u, student_id=sid, course='BSCS', year_level=2)

    def _app(self, stype, last, sid, status='Pending Validation'):
        return Application.objects.create(
            student=self._profile(last, sid),
            scholarship=Scholarship.objects.get(type=stype),
            status=status, form_data={},
        )

    # ── Reading ─────────────────────────────────────────────────────────────
    def test_tes_is_not_listed_on_the_page_the_nav_links_to(self):
        """The sidebar's Applications item points at /vpsea/affirmative/."""
        self._app('Academic', 'Cruz', '2024-0001')
        self._app('TES', 'Reyes', '2024-0002')

        r = self.c.get('/vpsea/affirmative/?tab=academic')
        self.assertEqual(r.status_code, 200)
        listed = [a.scholarship.type for a in r.context['academic_apps']]
        self.assertIn('Academic', listed)
        self.assertNotIn('TES', listed)
        self.assertNotContains(r, 'Reyes')

    def test_a_posted_tes_id_cannot_be_decided_there_either(self):
        tes = self._app('TES', 'Reyes', '2024-0002')
        self.c.post('/vpsea/affirmative/', {
            'tab': 'academic', 'app_id': tes.id,
            'status': 'Approved', 'remarks': 'should not stick',
        })
        tes.refresh_from_db()
        self.assertEqual(tes.status, 'Pending Validation')
        self.assertEqual(tes.remarks, '')

    def test_that_page_can_still_decide_its_own_programmes(self):
        acad = self._app('Academic', 'Cruz', '2024-0001')
        self.c.post('/vpsea/affirmative/', {
            'tab': 'academic', 'app_id': acad.id,
            'status': 'Approved', 'remarks': 'Verified',
        })
        acad.refresh_from_db()
        self.assertEqual(acad.status, 'Approved')
        self.assertEqual(acad.remarks, 'Verified')

    def test_the_other_programmes_are_still_listed(self):
        self._app('Academic', 'Cruz', '2024-0001')
        self._app('TDP', 'Lim', '2024-0003')
        r = self.c.get('/vpsea/affirmative/?tab=academic')
        listed = [a.scholarship.type for a in r.context['academic_apps']]
        self.assertCountEqual(listed, ['Academic', 'TDP'])

    def test_vpsea_never_reaches_the_tes_application_records(self):
        """The TES form itself — LRN, parents, disability — is UniFAST-only."""
        p = self._profile('Reyes', '2024-0004')
        TESApplication.objects.create(student=p, lrn='123456789012', status='Pending')
        r = self.c.get('/vpsea/affirmative/?tab=academic')
        self.assertNotIn('tes_applications', r.context)
        self.assertNotContains(r, '123456789012')

    def test_the_unifast_review_queue_is_closed_to_vpsea(self):
        r = self.c.get('/unifast/tes-applications/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    # ── Deciding ────────────────────────────────────────────────────────────
    def test_a_posted_tes_id_cannot_be_rejected_either(self):
        tes = self._app('TES', 'Reyes', '2024-0002', status='Approved')
        self.c.post('/vpsea/affirmative/', {
            'tab': 'academic', 'app_id': tes.id,
            'status': 'Rejected', 'remarks': 'nope',
        })
        tes.refresh_from_db()
        self.assertEqual(tes.status, 'Approved')

    def test_unifast_is_still_the_office_that_decides_tes(self):
        p = self._profile('Reyes', '2024-0005')
        tes = TESApplication.objects.create(student=p, status='Pending')
        User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
            password='pw', role='unifast')
        u = Client()
        u.login(email='unifast@bipsu.edu.ph', password='pw')
        u.post(f'/unifast/tes-applications/{tes.pk}/review/',
               {'status': 'Approved', 'remarks': 'ok'})
        tes.refresh_from_db()
        self.assertEqual(tes.status, 'Approved')
