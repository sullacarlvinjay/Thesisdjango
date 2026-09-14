from django.test import Client, TestCase

from api import scholar_columns
from api.models import (
    ImportedScholar, PartnerOffice, PartnerTableColumns, Scholarship,
    SystemSettings, User,
)


class PartnerColumnFixtures:
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        self.dost = Scholarship.objects.create(
            name='DOST Scholarship', type='DOST', category='application',
            description='x', eligibility='x', requirements=[],
            table_columns=['last_name', 'first_name', 'course'])
        ImportedScholar.objects.create(
            scholarship_type='DOST', term_label='26-1', last_name='Santos',
            first_name='Ana', course='BSCS', year_level=2, student_id='2024-0001')

        self.office = PartnerOffice.objects.create(name='DOST Region VIII')
        self.office.scholarships.set([self.dost])
        account = User.objects.create_user(
            username='dost@bipsu.edu.ph', email='dost@bipsu.edu.ph',
            password='pw', role='partner', first_name='DOST')
        account.partner_office = self.office
        account.save(update_fields=['partner_office'])
        self.c = Client()
        self.assertTrue(self.c.login(email='dost@bipsu.edu.ph', password='pw'))


class OverrideResolutionTest(PartnerColumnFixtures, TestCase):
    def test_no_override_means_the_offices_own_table(self):
        keys = [c['key'] for c in scholar_columns.resolve(
            self.dost, 'DOST', override=None)]
        self.assertEqual(keys, ['last_name', 'first_name', 'course'])

    def test_an_override_replaces_the_offices_choice(self):
        override = PartnerTableColumns.objects.create(
            office=self.office, scholarship=self.dost,
            table_columns=['course', 'last_name'])
        keys = [c['key'] for c in scholar_columns.resolve(
            self.dost, 'DOST', override=override)]
        self.assertEqual(keys, ['course', 'last_name'])

    def test_an_empty_override_falls_through_rather_than_showing_nothing(self):
        override = PartnerTableColumns.objects.create(
            office=self.office, scholarship=self.dost, table_columns=[])
        keys = [c['key'] for c in scholar_columns.resolve(
            self.dost, 'DOST', override=override)]
        self.assertEqual(keys, ['last_name', 'first_name', 'course'])

    def test_one_partner_per_programme(self):
        PartnerTableColumns.objects.create(
            office=self.office, scholarship=self.dost, table_columns=['course'])
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            PartnerTableColumns.objects.create(
                office=self.office, scholarship=self.dost, table_columns=['gwa'])


class PartnerSetsItsOwnLayoutTest(PartnerColumnFixtures, TestCase):
    PAGE = '/partner/columns/'

    def test_saving_a_layout_writes_only_the_partners_own_row(self):
        before = list(self.dost.table_columns)
        r = self.c.post(self.PAGE, {
            'type': 'DOST', 'table_columns': ['course', 'last_name']})
        self.assertEqual(r.status_code, 302)

        self.dost.refresh_from_db()
        self.assertEqual(self.dost.table_columns, before)
        row = PartnerTableColumns.objects.get(office=self.office, scholarship=self.dost)
        self.assertEqual(row.table_columns, ['course', 'last_name'])

    def test_the_partners_archive_renders_its_own_order(self):
        self.c.post(self.PAGE, {'type': 'DOST', 'table_columns': ['course', 'last_name']})
        r = self.c.get('/partner/archives/?type=DOST')
        keys = [c['key'] for c in r.context['columns']]
        self.assertEqual(keys, ['course', 'last_name'])
        self.assertTrue(r.context['uses_own_columns'])

    def test_the_download_matches_the_page(self):
        from io import BytesIO

        import openpyxl

        self.c.post(self.PAGE, {'type': 'DOST', 'table_columns': ['course', 'last_name']})
        r = self.c.get('/partner/reports/download/?type=DOST&sy=26-1')
        ws = openpyxl.load_workbook(BytesIO(r.content)).active
        headings = [c.value for c in ws[4] if c.value]
        self.assertEqual(headings, ['Course', 'Last Name'])

    def test_resetting_removes_the_row_rather_than_storing_an_empty_one(self):
        self.c.post(self.PAGE, {'type': 'DOST', 'table_columns': ['course']})
        self.c.post(self.PAGE, {'type': 'DOST', 'action': 'reset',
                                'table_columns': ['course']})
        self.assertFalse(PartnerTableColumns.objects.exists())

        r = self.c.get('/partner/archives/?type=DOST')
        self.assertFalse(r.context['uses_own_columns'])
        self.assertEqual([c['key'] for c in r.context['columns']],
                         ['last_name', 'first_name', 'course'])

    def test_saving_nothing_at_all_also_falls_back(self):
        self.c.post(self.PAGE, {'type': 'DOST', 'table_columns': ['course']})
        self.c.post(self.PAGE, {'type': 'DOST'})
        self.assertFalse(PartnerTableColumns.objects.exists())

    def test_a_partner_cannot_lay_out_a_programme_it_does_not_hold(self):
        other = Scholarship.objects.create(
            name='GSIS Scholarship', type='GSIS', category='application',
            description='x', eligibility='x', requirements=[])
        r = self.c.post(self.PAGE, {'type': 'GSIS', 'table_columns': ['course']})
        self.assertIn('error=', r['Location'])
        self.assertFalse(PartnerTableColumns.objects.filter(scholarship=other).exists())

    def test_one_partners_layout_is_not_anothers(self):
        second = PartnerOffice.objects.create(name='Second Funder')
        second.scholarships.set([self.dost])
        account = User.objects.create_user(
            username='two@bipsu.edu.ph', email='two@bipsu.edu.ph',
            password='pw', role='partner', first_name='Second')
        account.partner_office = second
        account.save(update_fields=['partner_office'])

        self.c.post(self.PAGE, {'type': 'DOST', 'table_columns': ['course', 'last_name']})

        other = Client()
        self.assertTrue(other.login(email='two@bipsu.edu.ph', password='pw'))
        r = other.get('/partner/archives/?type=DOST')
        self.assertFalse(r.context['uses_own_columns'])
        self.assertEqual([c['key'] for c in r.context['columns']],
                         ['last_name', 'first_name', 'course'])

    def test_the_endpoint_is_closed_to_everyone_but_partners(self):
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw', role='vpsea')
        sdso = Client()
        self.assertTrue(sdso.login(email='v@bipsu.edu.ph', password='pw'))
        sdso.post(self.PAGE, {'type': 'DOST', 'table_columns': ['course']})
        self.assertFalse(PartnerTableColumns.objects.exists())

    def test_the_office_still_sees_its_own_table_after_a_partner_rearranges(self):
        self.c.post(self.PAGE, {'type': 'DOST', 'table_columns': ['course', 'last_name']})

        User.objects.create_user(
            username='v2@bipsu.edu.ph', email='v2@bipsu.edu.ph', password='pw', role='vpsea')
        sdso = Client()
        self.assertTrue(sdso.login(email='v2@bipsu.edu.ph', password='pw'))
        r = sdso.get('/vpsea/archives/', {'type': 'DOST'})
        keys = [c['key'] for c in r.context['columns']]
        self.assertEqual(keys, ['last_name', 'first_name', 'course'])


class PickerShowsTheTableOrderTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))
        self.s = Scholarship.objects.create(
            name='DOST Scholarship', type='DOST', category='application',
            description='x', eligibility='x', requirements=[],
            table_columns=['course', 'last_name'])

    def test_the_chosen_columns_come_first_in_their_own_order(self):
        ctx = self.c.get(f'/vpsea/scholarships/{self.s.pk}/edit/').context
        catalogue = ctx['column_catalogue']
        self.assertEqual([c['key'] for c in catalogue[:2]], ['course', 'last_name'])
        self.assertEqual([c['position'] for c in catalogue[:2]], [0, 1])
        self.assertTrue(all(c['chosen'] for c in catalogue[:2]))
        self.assertFalse(any(c['chosen'] for c in catalogue[2:]))

    def test_an_unconfigured_programme_shows_its_default_table_already_ticked(self):
        blank = Scholarship.objects.create(
            name='Blank', type='Blank', category='application',
            description='x', eligibility='x', requirements=[])
        ctx = self.c.get(f'/vpsea/scholarships/{blank.pk}/edit/').context
        chosen = [c['key'] for c in ctx['column_catalogue'] if c['chosen']]
        self.assertEqual(chosen, scholar_columns.DEFAULT_COLUMNS)

    def test_the_form_saves_the_order_it_was_given(self):
        self.c.post(f'/vpsea/scholarships/{self.s.pk}/edit/', {
            'name': 'DOST Scholarship', 'type': 'DOST', 'description': 'x',
            'group': 'internal',
            'table_columns': ['gwa', 'last_name', 'course'],
        })
        self.s.refresh_from_db()
        self.assertEqual(self.s.table_columns, ['gwa', 'last_name', 'course'])
