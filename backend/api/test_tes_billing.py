"""The Billing tab: what CHED pays a grantee, and the statement that follows.

The rule this has to keep is the one that predates the tab. The amount columns
export blank unless an officer has entered a figure, because a rate the system
chose for itself would be a guess with a signature under it. The tab is where an
officer records what CHED told them — it is not where the system decides.

The arithmetic mirrors the workbook's own formulas, and the one worth reading
twice is the management fee: Form 2 computes `=SUM(N1101)*0.01`, one percent of
the TES benefits alone, so the disability top-ups sit outside it.
"""
from decimal import Decimal
from io import BytesIO

import openpyxl
from django.test import Client, TestCase

from api import tes_report
from api.models import (
    Scholarship, StudentProfile, SystemSettings, TESApplication, TESBilling, User,
)


class TESBillingTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        Scholarship.objects.create(
            name='TES', type='TES', category='application',
            description='x', eligibility='x', requirements=[])
        self.officer = User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
            password='pw', first_name='Uni', last_name='Fast', role='unifast')
        self.c = Client()
        self.assertTrue(self.c.login(email='unifast@bipsu.edu.ph', password='pw'))

    def _grantee(self, sid, pwd=False, school_year='2026-2027'):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph',
            password='pw', first_name='Juan', last_name=f'Cruz{sid}', role='student')
        p = StudentProfile.objects.create(user=u, student_id=sid, course='BSCS',
                                          year_level=2, gender='Male')
        return TESApplication.objects.create(
            student=p, status='Approved', school_year=school_year,
            semester='1st Semester', award_number=f'AW-{sid}',
            disability_type='Visual Disability' if pwd else 'N/A')

    def _rate(self, tes='10000', tes_3a='5000', year='2026-2027', **extra):
        return TESBilling.objects.update_or_create(
            school_year=year,
            defaults=dict(tes_amount=Decimal(tes) if tes else None,
                          tes_3a_amount=Decimal(tes_3a) if tes_3a else None,
                          **extra))[0]

    # ── The rule that predates the tab ──────────────────────────────────────

    def test_with_no_rate_the_amounts_still_export_blank(self):
        """Exactly what every year did before this page existed."""
        self._grantee('S1')
        row = tes_report.grantee_rows(school_year='2026-2027')[0]
        self.assertIsNone(row['tes_amount'])
        self.assertIsNone(row['tes_3a_amount'])

    def test_a_rate_for_another_year_does_not_bill_this_one(self):
        """CHED revises the figure; last year's must not leak into this year."""
        self._grantee('S1', school_year='2026-2027')
        self._rate(year='2025-2026')

        row = tes_report.grantee_rows(school_year='2026-2027')[0]
        self.assertIsNone(row['tes_amount'])

    def test_an_unscoped_report_bills_nothing(self):
        """'All school years' has no single rate, so it cannot have amounts."""
        self._grantee('S1')
        self._rate()
        self.assertIsNone(tes_report.grantee_rows()[0]['tes_amount'])

    # ── Who gets the top-up ─────────────────────────────────────────────────

    def test_the_disability_top_up_lands_only_on_those_rows(self):
        """Billing every grantee for it is the expensive mistake here."""
        self._grantee('S1', pwd=True)
        self._grantee('S2', pwd=False)
        self._rate()

        rows = {r['student_no']: r for r in tes_report.grantee_rows(school_year='2026-2027')}
        self.assertEqual(rows['S1']['tes_3a_amount'], Decimal('5000'))
        self.assertIsNone(rows['S2']['tes_3a_amount'])
        # Both are still billed the ordinary TES amount.
        self.assertEqual(rows['S1']['tes_amount'], Decimal('10000'))
        self.assertEqual(rows['S2']['tes_amount'], Decimal('10000'))

    # ── The arithmetic ──────────────────────────────────────────────────────

    def test_the_statement_matches_form_1(self):
        for sid in ('S1', 'S2', 'S3'):
            self._grantee(sid)
        self._grantee('S4', pwd=True)
        self._rate()

        s = tes_report.billing_summary('2026-2027')
        self.assertEqual(s['grantees'], 4)
        self.assertEqual(s['pwd'], 1)
        self.assertEqual(s['benefits'], Decimal('40000'))     # 4 x 10,000
        self.assertEqual(s['tes_3a'], Decimal('5000'))        # 1 x 5,000
        self.assertEqual(s['subtotal'], Decimal('45000'))
        self.assertEqual(s['total'], Decimal('45400'))

    def test_the_management_fee_is_one_percent_of_the_benefits_alone(self):
        """Form 2's own formula is =SUM(N1101)*0.01 — the top-ups are outside it."""
        self._grantee('S1', pwd=True)
        self._rate(tes='10000', tes_3a='5000')

        s = tes_report.billing_summary('2026-2027')
        self.assertEqual(s['fee'], Decimal('100.00'))          # 1% of 10,000
        self.assertNotEqual(s['fee'], Decimal('150.00'))       # not of 15,000

    def test_nothing_is_billable_without_a_rate_or_without_grantees(self):
        self._grantee('S1')
        self.assertFalse(tes_report.billing_summary('2026-2027')['ready'])

        self._rate()
        self.assertTrue(tes_report.billing_summary('2026-2027')['ready'])

        TESApplication.objects.update(status='Pending')
        self.assertFalse(tes_report.billing_summary('2026-2027')['ready'])

    # ── Into the workbook ───────────────────────────────────────────────────

    def test_the_amounts_reach_the_ched_workbook(self):
        self._grantee('S1', pwd=True)
        self._rate(reference_no='08-BiPSU-2026-1-2')

        r = self.c.get('/unifast/reports/download/tes/?sy=2026-2027')
        wb = openpyxl.load_workbook(BytesIO(r.content))
        form2, form1 = wb['Annex 2-Form 2'], wb['Annex 2-Form 1']

        self.assertEqual(form2['N31'].value, 10000)
        self.assertEqual(form2['O31'].value, 5000)
        self.assertEqual(form2['Q31'].value, 15000)           # the row total
        # The template's own totals formulas must survive being written around.
        self.assertEqual(form2['N1101'].value, '=SUM(N31:N1100)')
        self.assertEqual(form2['Q1102'].value, '=SUM(N1101)*0.01')
        self.assertEqual(form1['T10'].value, '08-BiPSU-2026-1-2')

    def test_without_a_rate_the_workbook_columns_are_still_empty(self):
        self._grantee('S1')
        r = self.c.get('/unifast/reports/download/tes/?sy=2026-2027')
        form2 = openpyxl.load_workbook(BytesIO(r.content))['Annex 2-Form 2']
        self.assertIsNone(form2['N31'].value)
        self.assertIsNone(form2['O31'].value)

    # ── The page ────────────────────────────────────────────────────────────

    def test_the_tab_is_in_the_unifast_nav(self):
        self.assertContains(self.c.get('/unifast/'), '/unifast/billing/')

    def test_saving_a_rate_records_who_and_when(self):
        r = self.c.post('/unifast/billing/', {
            'sy': '2026-2027', 'tes_amount': '10000', 'tes_3a_amount': '5000',
            'reference_no': '08-BiPSU-2026-1-2', 'statement_date': '2026-09-03'})
        self.assertEqual(r.status_code, 302)

        row = TESBilling.objects.get(school_year='2026-2027')
        self.assertEqual(row.tes_amount, Decimal('10000'))
        self.assertEqual(row.reference_no, '08-BiPSU-2026-1-2')
        self.assertEqual(row.updated_by, self.officer)

    def test_a_saved_rate_comes_back_in_the_boxes(self):
        """An empty string is not None, so a template fallback never fired."""
        self._rate(reference_no='08-BiPSU-2026-1-2')
        form = self.c.get('/unifast/billing/?sy=2026-2027').context['form']
        self.assertEqual(form['tes_amount'], Decimal('10000'))
        self.assertEqual(form['reference_no'], '08-BiPSU-2026-1-2')

    def test_a_rate_that_is_not_a_number_is_refused(self):
        r = self.c.post('/unifast/billing/',
                        {'sy': '2026-2027', 'tes_amount': 'ten thousand'})
        self.assertContains(r, 'must be a number')
        self.assertFalse(TESBilling.objects.exists())

    def test_a_negative_rate_is_refused(self):
        r = self.c.post('/unifast/billing/',
                        {'sy': '2026-2027', 'tes_amount': '-100'})
        self.assertContains(r, 'cannot be negative')
        self.assertFalse(TESBilling.objects.exists())

    def test_a_rate_typed_with_thousands_separators_is_taken(self):
        self.c.post('/unifast/billing/',
                    {'sy': '2026-2027', 'tes_amount': '10,000'})
        self.assertEqual(TESBilling.objects.get().tes_amount, Decimal('10000'))

    def test_clearing_the_amount_puts_the_year_back_to_blank(self):
        """A withdrawn advice has to be removable, not stuck at the old figure."""
        self._grantee('S1')
        self._rate()
        self.c.post('/unifast/billing/', {'sy': '2026-2027', 'tes_amount': ''})

        self.assertIsNone(TESBilling.objects.get().tes_amount)
        self.assertIsNone(tes_report.grantee_rows(school_year='2026-2027')[0]['tes_amount'])

    def test_the_page_defaults_to_the_active_term(self):
        r = self.c.get('/unifast/billing/')
        self.assertEqual(r.context['school_year'], '2026-2027')

    def test_billing_is_the_unifast_office_only(self):
        student = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            role='student')
        StudentProfile.objects.create(user=student, student_id='X1')
        c = Client()
        self.assertTrue(c.login(email='s@bipsu.edu.ph', password='pw'))
        self.assertNotEqual(c.get('/unifast/billing/').status_code, 200)
