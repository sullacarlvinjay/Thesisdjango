"""Outside funders with an account here, and the wall around what they see.

The SDSO runs the one office portal. A partner — DOST, GSIS, UniFAST, a
foundation — has standing of its own and a different job: it reads the archive
of its own scholars and takes a list away. What it may read is a decision the
SDSO records per partner, so most of what is worth testing is the boundary: a
partner must never reach another funder's scholars.
"""
from django.test import Client, TestCase

from api.models import (
    Application, ImportedScholar, PartnerOffice, Scholarship, StudentProfile,
    SystemSettings, User,
)

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class PartnerFixtures:
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        self.dost = Scholarship.objects.create(
            name='DOST S&T Undergraduate Scholarship', type='DOST',
            category='application', description='x', eligibility='x', requirements=[])
        self.gsis = Scholarship.objects.create(
            name='GSIS Scholarship', type='GSIS', category='application',
            description='x', eligibility='x', requirements=[])

        self.sdso = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw', role='vpsea')
        self.office = Client()
        self.assertTrue(self.office.login(email='v@bipsu.edu.ph', password='pw'))

    def _partner(self, name, email, scholarships=(), **kw):
        office = PartnerOffice.objects.create(name=name, **kw)
        office.scholarships.set(scholarships)
        account = User.objects.create_user(
            username=email, email=email, password='partner-pass',
            role='partner', first_name=name)
        account.partner_office = office
        account.save(update_fields=['partner_office'])
        client = Client()
        self.assertTrue(client.login(email=email, password='partner-pass'))
        return office, client

    def _scholar(self, stype, last, sid, term='26-1'):
        return ImportedScholar.objects.create(
            scholarship_type=stype, term_label=term, last_name=last,
            first_name='Test', student_id=sid, course='BSCS', year_level=2)


class SDSOManagesPartnersTest(PartnerFixtures, TestCase):
    PAGE = '/vpsea/partners/'

    def test_creating_a_partner_makes_the_account_that_signs_in_as_it(self):
        """An office nobody can log into is not something the SDSO ever wants,
        so both are made in one step and there is no window without a way in."""
        r = self.office.post(self.PAGE, {
            'action': 'create', 'name': 'DOST Region VIII',
            'email': 'dost@bipsu.edu.ph', 'password': 'a-good-password',
            'scholarships': [self.dost.pk],
        })
        self.assertEqual(r.status_code, 302)

        office = PartnerOffice.objects.get(name='DOST Region VIII')
        self.assertEqual(office.visible_types(), ['DOST'])
        account = User.objects.get(email='dost@bipsu.edu.ph')
        self.assertEqual(account.role, 'partner')
        self.assertEqual(account.partner_office, office)
        self.assertTrue(Client().login(email='dost@bipsu.edu.ph', password='a-good-password'))

    def test_a_partner_can_be_created_with_no_access_at_all(self):
        """The safe default: nothing ticked means an empty portal, never
        everyone's scholars."""
        self.office.post(self.PAGE, {
            'action': 'create', 'name': 'New Foundation',
            'email': 'nf@bipsu.edu.ph', 'password': 'a-good-password'})
        self.assertEqual(
            PartnerOffice.objects.get(name='New Foundation').visible_types(), [])

    def test_a_short_password_is_refused(self):
        r = self.office.post(self.PAGE, {
            'action': 'create', 'name': 'X', 'email': 'x@bipsu.edu.ph', 'password': 'short'})
        self.assertIn('error=', r['Location'])
        self.assertFalse(PartnerOffice.objects.filter(name='X').exists())

    def test_a_duplicate_name_or_email_is_refused(self):
        self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        for field, value in (('name', 'DOST'), ('email', 'dost@bipsu.edu.ph')):
            data = {'action': 'create', 'name': 'Other', 'password': 'a-good-password',
                    'email': 'other@bipsu.edu.ph'}
            data[field] = value
            r = self.office.post(self.PAGE, data)
            self.assertIn('error=', r['Location'], field)
        self.assertEqual(PartnerOffice.objects.count(), 1)

    def test_the_office_changes_what_a_partner_can_see(self):
        office, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        self.office.post(self.PAGE, {
            'action': 'access', 'office_id': office.pk,
            'scholarships': [self.dost.pk, self.gsis.pk],
            'may_add_scholarships': 'on'})
        office.refresh_from_db()
        self.assertEqual(sorted(office.visible_types()), ['DOST', 'GSIS'])
        self.assertTrue(office.may_add_scholarships)

    def test_access_can_be_taken_away_again(self):
        office, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        self.office.post(self.PAGE, {'action': 'access', 'office_id': office.pk})
        office.refresh_from_db()
        self.assertEqual(office.visible_types(), [])

    def test_a_partner_can_be_renamed(self):
        office, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        self.office.post(self.PAGE, {
            'action': 'access', 'office_id': office.pk, 'name': 'DOST Region VIII',
            'scholarships': [self.dost.pk]})
        office.refresh_from_db()
        self.assertEqual(office.name, 'DOST Region VIII')
        self.assertEqual(office.visible_types(), ['DOST'])

    def test_a_rename_onto_another_partners_name_is_refused(self):
        first, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        second, _ = self._partner('GSIS', 'gsis@bipsu.edu.ph', [self.gsis])
        r = self.office.post(self.PAGE, {
            'action': 'access', 'office_id': second.pk, 'name': 'DOST'})
        self.assertIn('error=', r['Location'])
        second.refresh_from_db()
        self.assertEqual(second.name, 'GSIS')

    def test_a_blank_name_is_refused(self):
        office, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        r = self.office.post(self.PAGE, {
            'action': 'access', 'office_id': office.pk, 'name': '  '})
        self.assertIn('error=', r['Location'])
        office.refresh_from_db()
        self.assertEqual(office.name, 'DOST')

    def test_the_office_resets_a_partners_password(self):
        """Set here and told to the partner directly; nothing emails it, so
        there is no reset link for an outside body to lose."""
        office, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        account = office.accounts.get()
        self.office.post(self.PAGE, {
            'action': 'password', 'office_id': office.pk,
            'account_id': account.pk, 'password': 'a-new-password'})
        self.assertTrue(Client().login(email='dost@bipsu.edu.ph', password='a-new-password'))

    def test_a_short_reset_password_is_refused(self):
        office, client = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        account = office.accounts.get()
        r = self.office.post(self.PAGE, {
            'action': 'password', 'office_id': office.pk,
            'account_id': account.pk, 'password': 'short'})
        self.assertIn('error=', r['Location'])
        self.assertTrue(Client().login(email='dost@bipsu.edu.ph', password='partner-pass'))

    def test_a_password_cannot_be_set_on_another_partners_account(self):
        one, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        two, _ = self._partner('GSIS', 'gsis@bipsu.edu.ph', [self.gsis])
        theirs = two.accounts.get()
        r = self.office.post(self.PAGE, {
            'action': 'password', 'office_id': one.pk,
            'account_id': theirs.pk, 'password': 'a-new-password'})
        self.assertIn('error=', r['Location'])
        self.assertTrue(Client().login(email='gsis@bipsu.edu.ph', password='partner-pass'))

    def test_deleting_a_partner_takes_its_accounts_with_it(self):
        """A login whose office is gone reaches nothing — leaving it behind is
        an account that exists and does nothing."""
        office, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        r = self.office.post(self.PAGE, {'action': 'delete', 'office_id': office.pk})
        self.assertIn('deleted=', r['Location'])
        self.assertFalse(PartnerOffice.objects.filter(pk=office.pk).exists())
        self.assertFalse(User.objects.filter(email='dost@bipsu.edu.ph').exists())

    def test_deleting_a_partner_leaves_the_scholars_alone(self):
        """They belong to the programme, not to the funder reading them."""
        self._scholar('DOST', 'Santos', '2024-0500')
        office, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        self.office.post(self.PAGE, {'action': 'delete', 'office_id': office.pk})
        self.assertTrue(ImportedScholar.objects.filter(last_name='Santos').exists())
        self.assertTrue(Scholarship.objects.filter(type='DOST').exists())

    def test_only_the_sdso_deletes_a_partner(self):
        office, partner = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        partner.post(self.PAGE, {'action': 'delete', 'office_id': office.pk})
        self.assertTrue(PartnerOffice.objects.filter(pk=office.pk).exists())

    def test_suspending_a_partner_keeps_the_account_but_shuts_the_portal(self):
        office, client = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        self.office.post(self.PAGE, {'action': 'toggle', 'office_id': office.pk})

        office.refresh_from_db()
        self.assertFalse(office.is_active)
        self.assertTrue(User.objects.filter(email='dost@bipsu.edu.ph').exists())
        self.assertEqual(client.get('/partner/').status_code, 302)

    def test_removing_the_office_does_not_delete_its_people(self):
        """SET_NULL, not CASCADE: the account survives, unable to reach the
        portal, and the office decides what to do with it."""
        office, _ = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        office.delete()
        account = User.objects.get(email='dost@bipsu.edu.ph')
        self.assertIsNone(account.partner_office)

    def test_the_screen_is_the_sdsos_alone(self):
        _, partner = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        User.objects.create_user(
            username='u@bipsu.edu.ph', email='u@bipsu.edu.ph', password='pw', role='nsu_staff')
        staff = Client()
        self.assertTrue(staff.login(email='u@bipsu.edu.ph', password='pw'))
        for client in (partner, staff, Client()):
            self.assertNotEqual(client.get(self.PAGE).status_code, 200)

    def test_another_office_cannot_grant_itself_access(self):
        office, partner = self._partner('DOST', 'dost@bipsu.edu.ph', [])
        partner.post(self.PAGE, {
            'action': 'access', 'office_id': office.pk, 'scholarships': [self.gsis.pk]})
        office.refresh_from_db()
        self.assertEqual(office.visible_types(), [])


class PartnerSeesOnlyItsOwnTest(PartnerFixtures, TestCase):
    """The boundary that matters."""

    def setUp(self):
        super().setUp()
        self._scholar('DOST', 'Santos', '2024-0001')
        self._scholar('GSIS', 'Reyes', '2024-0002')
        self.office_row, self.dost_client = self._partner(
            'DOST Region VIII', 'dost@bipsu.edu.ph', [self.dost])

    def test_the_archive_shows_its_own_scholars(self):
        r = self.dost_client.get('/partner/archives/?type=DOST')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Santos')
        self.assertNotContains(r, 'Reyes')

    def test_asking_for_another_funders_programme_falls_back_to_its_own(self):
        """Not a 500 and not an empty page: the tab it asked for is not one it
        has, so it lands on one it does."""
        r = self.dost_client.get('/partner/archives/?type=GSIS')
        self.assertEqual(r.context['active_type'], 'DOST')
        self.assertNotContains(r, 'Reyes')

    def test_the_tabs_are_only_its_own_programmes(self):
        r = self.dost_client.get('/partner/archives/')
        self.assertEqual(r.context['archive_types'], ['DOST'])

    def test_the_dashboard_counts_only_its_own(self):
        r = self.dost_client.get('/partner/')
        self.assertEqual([p['scholarship'].type for p in r.context['programmes']], ['DOST'])

    def test_a_partner_with_no_access_sees_an_empty_portal_not_everyones(self):
        """The failure that matters is the one where a funder reads another
        funder's scholars, so nothing is the default."""
        _, empty = self._partner('New Foundation', 'nf@bipsu.edu.ph', [])
        r = empty.get('/partner/archives/')
        self.assertEqual(r.context['archive_types'], [])
        self.assertNotContains(r, 'Santos')
        self.assertNotContains(r, 'Reyes')
        self.assertFalse(empty.get('/partner/').context['has_access'])

    def test_the_download_refuses_a_programme_it_does_not_hold(self):
        r = self.dost_client.get('/partner/reports/download/?type=GSIS')
        self.assertEqual(r.status_code, 302)
        self.assertIn('error=', r['Location'])

    def test_the_download_gives_its_own_programme(self):
        r = self.dost_client.get('/partner/reports/download/?type=DOST&sy=26-1')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], XLSX)
        self.assertIn('.xlsx', r['Content-Disposition'])

    def test_the_workbook_carries_its_own_scholars_and_no_others(self):
        from io import BytesIO

        import openpyxl

        r = self.dost_client.get('/partner/reports/download/?type=DOST&sy=26-1')
        wb = openpyxl.load_workbook(BytesIO(r.content))
        text = '\n'.join(str(c.value) for row in wb.active.iter_rows()
                         for c in row if c.value is not None)
        self.assertIn('Santos', text)
        self.assertNotIn('Reyes', text)
        self.assertIn('DOST Region VIII', text)

    def test_a_partner_reaches_no_office_portal(self):
        for url in ('/vpsea/', '/vpsea/archives/', '/vpsea/reports/',
                    '/vpsea/partners/'):
            self.assertNotEqual(self.dost_client.get(url).status_code, 200, url)

    def test_the_partner_portal_is_closed_to_everyone_else(self):
        User.objects.create_user(
            username='u@bipsu.edu.ph', email='u@bipsu.edu.ph', password='pw', role='nsu_staff')
        staff = Client()
        self.assertTrue(staff.login(email='u@bipsu.edu.ph', password='pw'))
        for client in (self.office, staff, Client()):
            for url in ('/partner/', '/partner/archives/',
                        '/partner/reports/download/?type=DOST'):
                self.assertNotEqual(client.get(url).status_code, 200, url)

    def test_a_partner_account_with_no_office_cannot_get_in(self):
        stray = User.objects.create_user(
            username='stray@bipsu.edu.ph', email='stray@bipsu.edu.ph',
            password='pw', role='partner')
        self.assertIsNone(stray.partner_office)
        client = Client()
        self.assertTrue(client.login(email='stray@bipsu.edu.ph', password='pw'))
        self.assertEqual(client.get('/partner/').status_code, 302)

    def test_a_partner_collects_nothing(self):
        """The portal is a window onto the archive, not a second place to
        apply. It briefly had a form builder and a submissions queue; the SDSO
        decided a funder that wants its own questions asks them on its own site,
        and the office records the award here once it is granted."""
        for url in ('/partner/form/', '/partner/submissions/',
                    '/partner/submissions/download/?type=DOST',
                    '/student/apply/partner/DOST/'):
            self.assertEqual(self.dost_client.get(url).status_code, 404, url)

    def test_the_sidebar_offers_only_what_is_left(self):
        """A nav link to a route that 404s is worse than no link."""
        text = self.dost_client.get('/partner/').content.decode()
        self.assertIn('/partner/archives/', text)
        self.assertNotIn('/partner/form/', text)
        self.assertNotIn('/partner/submissions/', text)


class PartnerReadsApplicationsTooTest(PartnerFixtures, TestCase):
    """Not only imported rows: a programme reviewed in the portal counts too."""

    def test_an_approved_application_appears_beside_the_imported_rows(self):
        u = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Villanueva', role='student')
        profile = StudentProfile.objects.create(
            user=u, student_id='2024-0100', course='BSCS', year_level=2)
        Application.objects.create(
            student=profile, scholarship=self.dost, status='Approved', term_label='26-1')
        self._scholar('DOST', 'Santos', '2024-0001')

        _, client = self._partner('DOST', 'dost@bipsu.edu.ph', [self.dost])
        r = client.get('/partner/archives/?type=DOST&sy=26-1')
        self.assertContains(r, 'Villanueva')
        self.assertContains(r, 'Santos')
        self.assertEqual(r.context['total'], 2)


class OneDownloadNotTwoTest(PartnerFixtures, TestCase):
    """The Reports tab is gone; the download it offered lives on the Scholars tab.

    Both tabs listed the partner's own programmes behind the same workbook, so a
    funder could take the same file away from two places and the second one
    carried nothing the first did not.
    """

    def setUp(self):
        super().setUp()
        self._scholar('DOST', 'Santos', '2024-0001')
        self.office_row, self.dost_client = self._partner(
            'DOST Region VIII', 'dost@bipsu.edu.ph', [self.dost])

    def test_the_reports_page_is_gone(self):
        self.assertEqual(self.dost_client.get('/partner/reports/').status_code, 404)

    def test_the_portal_no_longer_offers_it(self):
        for page in ('/partner/', '/partner/archives/', '/partner/profile/'):
            html = self.dost_client.get(page).content.decode()
            self.assertNotIn('/partner/reports/"', html, page)
            self.assertNotIn('>Reports<', html, page)

    def test_the_scholars_tab_still_offers_the_download(self):
        html = self.dost_client.get('/partner/archives/?type=DOST').content.decode()
        self.assertIn('Download Excel', html)
        self.assertIn('/partner/reports/download/?type=DOST', html)

    def test_the_download_itself_still_works(self):
        r = self.dost_client.get('/partner/reports/download/?type=DOST&sy=26-1')
        self.assertEqual(r.status_code, 200)
        self.assertIn('.xlsx', r['Content-Disposition'])

    def test_a_refused_download_lands_on_the_scholars_tab(self):
        """It used to send the funder to a page that no longer exists."""
        r = self.dost_client.get('/partner/reports/download/?type=GSIS')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('/partner/archives/'), r['Location'])
        self.assertIn('error=', r['Location'])
        self.assertEqual(self.dost_client.get(r['Location']).status_code, 200)
