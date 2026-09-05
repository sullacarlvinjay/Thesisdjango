"""The Liquidation tab: what CHED's money did once it arrived.

Billing states what the office asked CHEDRO for. This states what was remitted,
what the cashier released, and what is still in hand — three facts that
routinely disagree, which is the entire reason they are recorded separately.

The rules worth keeping, and what breaks if they go:

* **Nothing is assumed from the billed rate.** A liquidation that fills itself
  in at the billed amount reconciles perfectly every time and therefore cannot
  detect the thing it exists to detect. A grantee nobody has accounted for is
  reported as outstanding, never as paid and never as zero.
* **The grantee list is the billing's list.** The page accounts for exactly the
  people the office billed for, read from the database on every save, so a
  posted row for anyone else records nothing.
* **Only a release carries money.** A row moved back to Unclaimed drops its
  amount, or the totals go on counting a payment that was retracted.
"""
from decimal import Decimal

from django.test import Client, TestCase

from api import tes_report
from api.models import (
    Scholarship, StudentProfile, SystemSettings, TESApplication, TESBilling,
    TESDisbursement, TESLiquidation, User,
)


class TESLiquidationTest(TestCase):
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

    # ── Fixtures ────────────────────────────────────────────────────────────

    def _grantee(self, sid, pwd=False, school_year='2026-2027', status='Approved'):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph',
            password='pw', first_name='Juan', last_name=f'Cruz{sid}', role='student')
        p = StudentProfile.objects.create(user=u, student_id=sid, course='BSCS',
                                          year_level=2, gender='Male')
        return TESApplication.objects.create(
            student=p, status=status, school_year=school_year,
            semester='1st Semester', award_number=f'AW-{sid}',
            disability_type='Visual Disability' if pwd else 'N/A')

    def _rate(self, tes='10000', tes_3a='5000', year='2026-2027'):
        return TESBilling.objects.update_or_create(
            school_year=year,
            defaults=dict(tes_amount=Decimal(tes) if tes else None,
                          tes_3a_amount=Decimal(tes_3a) if tes_3a else None))[0]

    def _remit(self, amount='20000', year='2026-2027'):
        return TESLiquidation.objects.update_or_create(
            school_year=year,
            defaults=dict(funds_received=Decimal(amount) if amount else None))[0]

    def _release(self, liquidation, app, amount='10000', status='Released'):
        return TESDisbursement.objects.create(
            liquidation=liquidation, tes_application=app, status=status,
            amount_released=Decimal(amount) if amount else None)

    # ── Nothing is assumed ──────────────────────────────────────────────────

    def test_a_grantee_with_no_row_is_outstanding_not_paid(self):
        """The rule the whole page rests on: silence is not a payment."""
        self._grantee('S1')
        self._rate()
        self._remit()

        summary = tes_report.liquidation_summary('2026-2027')
        self.assertEqual(summary['unaccounted'], 1)
        self.assertEqual(summary['released'], Decimal('0'))
        self.assertEqual(summary['released_count'], 0)
        self.assertFalse(summary['settled'])

    def test_an_unaccounted_grantee_is_not_counted_as_zero(self):
        """Zero released is a claim; no row at all is 'nobody has said yet'."""
        self._grantee('S1')
        rows = tes_report.liquidation_rows('2026-2027')
        self.assertIsNone(rows[0]['disbursement'])

    def test_balance_is_none_until_a_remittance_is_recorded(self):
        """Better than reporting the whole payout owed on a term nobody touched."""
        self._grantee('S1')
        self._rate()
        self.assertIsNone(tes_report.liquidation_summary('2026-2027')['balance'])

    # ── The reconciliation ──────────────────────────────────────────────────

    def test_balance_is_what_arrived_less_what_went_out(self):
        self._grantee('S1')
        self._grantee('S2')
        self._rate()
        liq = self._remit('20000')
        apps = list(TESApplication.objects.order_by('student__student_id'))
        self._release(liq, apps[0], '10000')

        summary = tes_report.liquidation_summary('2026-2027')
        self.assertEqual(summary['received'], Decimal('20000'))
        self.assertEqual(summary['released'], Decimal('10000'))
        self.assertEqual(summary['balance'], Decimal('10000'))

    def test_a_returned_row_reduces_the_balance_too(self):
        """Money sent back to CHED has left the office as surely as a release."""
        self._grantee('S1')
        self._rate()
        liq = self._remit('10000')
        self._release(liq, TESApplication.objects.get(), '10000', status='Returned')

        summary = tes_report.liquidation_summary('2026-2027')
        self.assertEqual(summary['returned'], Decimal('10000'))
        self.assertEqual(summary['released'], Decimal('0'))
        self.assertEqual(summary['balance'], Decimal('0'))

    def test_unclaimed_money_stays_inside_the_balance(self):
        """It is still the office's to hold, so it is not subtracted anywhere."""
        self._grantee('S1')
        self._rate()
        liq = self._remit('10000')
        self._release(liq, TESApplication.objects.get(), None, status='Unclaimed')

        summary = tes_report.liquidation_summary('2026-2027')
        self.assertEqual(summary['unclaimed_count'], 1)
        self.assertEqual(summary['released'], Decimal('0'))
        self.assertEqual(summary['balance'], Decimal('10000'))
        self.assertFalse(summary['settled'])

    def test_settled_only_when_everyone_is_accounted_for_and_nothing_is_held(self):
        self._grantee('S1')
        self._rate()
        liq = self._remit('10000')
        self._release(liq, TESApplication.objects.get(), '10000')

        summary = tes_report.liquidation_summary('2026-2027')
        self.assertTrue(summary['settled'])
        self.assertEqual(summary['balance'], Decimal('0'))

    def test_releasing_more_than_arrived_is_flagged_not_printed_as_a_negative(self):
        self._grantee('S1')
        self._rate()
        liq = self._remit('5000')
        self._release(liq, TESApplication.objects.get(), '10000')

        summary = tes_report.liquidation_summary('2026-2027')
        self.assertTrue(summary['over_released'])
        self.assertFalse(summary['settled'])

    # ── Scoped to one term ──────────────────────────────────────────────────

    def test_another_year_is_neither_counted_nor_reconciled_here(self):
        """A balance spanning two terms reconciles to a number nobody can explain."""
        self._grantee('S1', school_year='2026-2027')
        self._grantee('S2', school_year='2025-2026')

        summary = tes_report.liquidation_summary('2026-2027')
        self.assertEqual(summary['grantees'], 1)

    def test_only_approved_grantees_are_liquidated(self):
        self._grantee('S1')
        self._grantee('S2', status='Pending')
        self.assertEqual(tes_report.liquidation_summary('2026-2027')['grantees'], 1)

    # ── What the billing said, beside what was paid ─────────────────────────

    def test_the_billed_entitlement_is_shown_per_grantee(self):
        self._grantee('S1', pwd=True)
        self._rate(tes='10000', tes_3a='5000')

        row = tes_report.liquidation_rows('2026-2027')[0]
        self.assertEqual(row['entitled'], Decimal('15000'))

    def test_with_no_rate_there_is_nothing_to_compare_against(self):
        """The Billing tab's blank export, seen from this side."""
        self._grantee('S1')
        row = tes_report.liquidation_rows('2026-2027')[0]
        self.assertIsNone(row['entitled'])
        self.assertIsNone(tes_report.liquidation_summary('2026-2027')['billed'])

    # ── The page ────────────────────────────────────────────────────────────

    def test_the_tab_is_reachable_and_lists_its_grantees(self):
        self._grantee('S1')
        self._rate()
        html = self.c.get('/unifast/liquidation/?sy=2026-2027').content.decode()
        self.assertContains(self.c.get('/unifast/liquidation/'), 'TES Liquidation')
        self.assertIn('CruzS1', html)

    def test_the_tab_is_in_the_unifast_nav(self):
        html = self.c.get('/unifast/').content.decode()
        self.assertIn('/unifast/liquidation/', html)

    def test_only_the_unifast_office_may_open_it(self):
        """Same boundary every other tab in this portal keeps."""
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        other = Client()
        self.assertTrue(other.login(email='v@bipsu.edu.ph', password='pw'))
        self.assertEqual(other.get('/unifast/liquidation/').status_code, 302)
        self.assertEqual(Client().get('/unifast/liquidation/').status_code, 302)

    # ── Saving ──────────────────────────────────────────────────────────────

    def test_recording_a_remittance(self):
        self._grantee('S1')
        response = self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'remittance',
            'funds_received': '20,000.00', 'received_date': '2026-09-01',
            'credit_advice_no': 'CA-1', 'report_no': 'LR-1',
        })
        self.assertEqual(response.status_code, 302)

        row = TESLiquidation.objects.get(school_year='2026-2027')
        # Typed with a thousands separator, as it is read off a voucher.
        self.assertEqual(row.funds_received, Decimal('20000.00'))
        self.assertEqual(row.credit_advice_no, 'CA-1')
        self.assertEqual(row.updated_by, self.officer)

    def test_a_remittance_that_is_not_a_number_is_refused_with_a_reason(self):
        html = self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'remittance', 'funds_received': 'twenty',
        }).content.decode()
        self.assertIn('must be a number', html)
        self.assertFalse(TESLiquidation.objects.filter(funds_received__isnull=False).exists())

    def test_a_negative_remittance_is_refused(self):
        html = self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'remittance', 'funds_received': '-100',
        }).content.decode()
        self.assertIn('cannot be negative', html)

    def test_recording_a_release_against_a_grantee(self):
        app = self._grantee('S1')
        self._rate()
        response = self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements',
            f'status-{app.id}': 'Released',
            f'amount-{app.id}': '10000',
            f'date-{app.id}': '2026-09-02',
            f'receipt-{app.id}': 'OR-77',
        })
        self.assertEqual(response.status_code, 302)

        d = TESDisbursement.objects.get()
        self.assertEqual(d.amount_released, Decimal('10000'))
        self.assertEqual(d.receipt_no, 'OR-77')
        self.assertTrue(d.is_released)

    def test_releases_save_without_a_remittance_on_file(self):
        """The office often pays before the credit advice is filed."""
        app = self._grantee('S1')
        self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements',
            f'status-{app.id}': 'Released', f'amount-{app.id}': '10000',
        })
        self.assertTrue(TESDisbursement.objects.exists())
        self.assertIsNone(TESLiquidation.objects.get().funds_received)

    def test_a_row_moved_back_to_unclaimed_keeps_no_amount(self):
        """Or the totals go on counting a payment that was retracted."""
        app = self._grantee('S1')
        self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements',
            f'status-{app.id}': 'Released', f'amount-{app.id}': '10000',
        })
        self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements',
            f'status-{app.id}': 'Unclaimed', f'amount-{app.id}': '10000',
        })

        d = TESDisbursement.objects.get()
        self.assertIsNone(d.amount_released)
        self.assertIsNone(d.date_released)
        self.assertEqual(tes_report.liquidation_summary('2026-2027')['released'],
                         Decimal('0'))

    def test_a_row_left_blank_records_nothing(self):
        """Saving the page without touching a grantee must not account for them."""
        app = self._grantee('S1')
        self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements', f'status-{app.id}': '',
        })
        self.assertFalse(TESDisbursement.objects.exists())

    def test_a_row_posted_for_somebody_elses_grantee_records_nothing(self):
        """The list is read from the database, not from the form."""
        mine = self._grantee('S1', school_year='2026-2027')
        theirs = self._grantee('S2', school_year='2025-2026')
        self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements',
            f'status-{mine.id}': 'Released', f'amount-{mine.id}': '10000',
            f'status-{theirs.id}': 'Released', f'amount-{theirs.id}': '10000',
        })
        self.assertEqual(TESDisbursement.objects.count(), 1)
        self.assertEqual(TESDisbursement.objects.get().tes_application_id, mine.id)

    def test_a_release_with_no_amount_is_refused(self):
        """Otherwise it reports as one grantee paid PhP 0.00, which reads as a
        payment of zero rather than as the omission it is."""
        app = self._grantee('S1')
        html = self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements',
            f'status-{app.id}': 'Released', f'amount-{app.id}': '',
        }).content.decode()
        self.assertIn('needs the amount that was paid', html)
        self.assertFalse(TESDisbursement.objects.exists())

    def test_the_other_statuses_need_no_amount(self):
        """Only a release moves money, so only a release has to state a figure."""
        app = self._grantee('S1')
        self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements',
            f'status-{app.id}': 'Unclaimed', f'amount-{app.id}': '',
        })
        self.assertEqual(TESDisbursement.objects.get().status, 'Unclaimed')

    def test_a_status_this_office_does_not_use_is_refused(self):
        app = self._grantee('S1')
        html = self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements',
            f'status-{app.id}': 'Embezzled', f'amount-{app.id}': '10000',
        }).content.decode()
        self.assertIn('status this office does not use', html)
        self.assertFalse(TESDisbursement.objects.exists())

    def test_the_same_fault_on_many_rows_is_reported_once(self):
        """Ten identical lines tell the officer nothing the first one did not."""
        a, b = self._grantee('S1'), self._grantee('S2')
        html = self.c.post('/unifast/liquidation/', {
            'sy': '2026-2027', 'action': 'disbursements',
            f'status-{a.id}': 'Released', f'amount-{a.id}': '',
            f'status-{b.id}': 'Released', f'amount-{b.id}': '',
        }).content.decode()
        self.assertEqual(html.count('needs the amount that was paid'), 1)

    def test_saving_the_same_grantee_twice_updates_one_row(self):
        """The unique constraint, seen from the view: no double-counting."""
        app = self._grantee('S1')
        for amount in ('10000', '8000'):
            self.c.post('/unifast/liquidation/', {
                'sy': '2026-2027', 'action': 'disbursements',
                f'status-{app.id}': 'Released', f'amount-{app.id}': amount,
            })
        self.assertEqual(TESDisbursement.objects.count(), 1)
        self.assertEqual(TESDisbursement.objects.get().amount_released, Decimal('8000'))

    def test_saved_figures_render_back_into_the_form(self):
        """The trap the Billing tab hit: '' is not None, so a template default
        never fires and a saved figure renders blank."""
        self._remit('20000')
        html = self.c.get('/unifast/liquidation/?sy=2026-2027').content.decode()
        self.assertIn('20000.00', html)
