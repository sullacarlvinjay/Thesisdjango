"""Award numbers come from the funding agency, and are read from their column.

Nothing in the system generates an award number. Every write is either typed by
an officer or read out of the agency's own spreadsheet, which is correct: the
university does not decide these.

What is pinned here is a regression. Promoting award_number and
congress_district out of Application.form_data moved the Python readers but left
the *template* readers on the old JSON path, so an award created afterwards
rendered as a blank cell — no error, just a missing number on an official list.
These tests render the real page and look for the value.
"""
from django.test import Client, TestCase

from api.models import (
    Application, Scholarship, StudentProfile, SystemSettings, User,
)


class AwardNumberTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        for stype, name in (('TDP', 'TDP Scholarship'),
                            ('CHED', 'CHED Merit'),
                            ('Academic', 'Academic Scholarship')):
            Scholarship.objects.create(
                name=name, type=stype, category='application',
                description='x', eligibility='x', requirements=[],
            )
        User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))

    def _award(self, stype, last='Santos', sid='2024-0001', award='', cong=''):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph', password='pw',
            first_name='Test', last_name=last, role='student',
        )
        p = StudentProfile.objects.create(
            user=u, student_id=sid, course='BSCS', year_level=2,
            barangay='Poblacion', municipality='Naval', province='Biliran')
        return Application.objects.create(
            student=p, scholarship=Scholarship.objects.get(type=stype),
            status='Approved', term_label='26-1',
            award_number=award, congress_district=cong,
        )

    # ── nothing invents an award number ─────────────────────────────────────

    def test_an_award_number_is_never_generated(self):
        """A new award starts blank. The agency issues the number, not us."""
        app = self._award('TDP', last='Blank', sid='2024-0009')
        self.assertEqual(app.award_number, '')
        app.refresh_from_db()
        self.assertEqual(app.award_number, '')

    # ── the column, not the JSON ────────────────────────────────────────────

    def test_an_award_number_on_the_column_reaches_the_page(self):
        """The Tier 2 regression: writers moved to the column, readers did not."""
        self._award('TDP', last='Reyes', sid='2024-0002',
                    award='TDP-2026-0042', cong='Lone District')
        r = self.c.get('/vpsea/archives/?type=TDP')
        self.assertContains(r, 'TDP-2026-0042')
        self.assertContains(r, 'Lone District')

    def test_an_award_number_left_in_old_form_data_is_not_read_instead(self):
        """form_data may still hold a stale copy from before the migration."""
        app = self._award('TDP', last='Cruz', sid='2024-0003', award='NEW-0001')
        app.form_data = {'award_number': 'STALE-9999'}
        app.save()
        r = self.c.get('/vpsea/archives/?type=TDP')
        self.assertContains(r, 'NEW-0001')
        self.assertNotContains(r, 'STALE-9999')

    # ── TES belongs to UniFAST, and only there ──────────────────────────────

    def test_unifast_records_an_award_number_for_tes(self):
        """CHED issues TES award numbers, and UniFAST administers TES."""
        Scholarship.objects.create(
            name='Tertiary Education Subsidy', type='TES', category='application',
            description='x', eligibility='x', requirements=[],
        )
        self._award('TES', last='Uy', sid='2024-0005', award='TES-2026-0001')
        User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
            password='pw', role='unifast',
        )
        office = Client()
        self.assertTrue(office.login(email='unifast@bipsu.edu.ph', password='pw'))

        r = office.get('/unifast/archives/?type=TES')
        self.assertContains(r, 'Award No.')
        self.assertContains(r, 'TES-2026-0001')
        self.assertContains(r, 'name="award_number"')

    def test_the_sdso_archives_do_not_offer_an_award_number_for_tes(self):
        """The SDSO side of the house does not carry one for this programme."""
        Scholarship.objects.create(
            name='Tertiary Education Subsidy', type='TES', category='application',
            description='x', eligibility='x', requirements=[],
        )
        self._award('TES', last='Lim', sid='2024-0006')
        r = self.c.get('/vpsea/archives/?type=TES')
        self.assertNotContains(r, 'Award No.')

    # ── round trip through the office's edit screen ─────────────────────────

    def test_the_office_can_record_the_agencys_award_number(self):
        app = self._award('CHED', last='Lim', sid='2024-0004')
        self.c.post(f'/vpsea/archives/{app.pk}/edit/', {
            'scholarship_type': 'CHED',
            'first_name': 'Test', 'last_name': 'Lim',
            'course': 'BSCS', 'year_level': '2',
            'award_number': 'CHED-2026-0777',
        })
        app.refresh_from_db()
        self.assertEqual(app.award_number, 'CHED-2026-0777')

        r = self.c.get('/vpsea/archives/?type=CHED')
        self.assertContains(r, 'CHED-2026-0777')
