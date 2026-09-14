from django.test import Client, TestCase

from api.models import (
    ActivityLog, Application, ImportedScholar, PartnerOffice, Scholarship,
    StudentProfile, SystemSettings, User,
)


class PartnerScholarFixtures:
    URL = '/partner/scholars/'
    PAGE = '/partner/archives/'

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.dost = Scholarship.objects.create(
            name='DOST Scholarship', type='DOST', category='application',
            description='x', eligibility='x', requirements=[])
        self.ched = Scholarship.objects.create(
            name='CHED Merit', type='CHED', category='application',
            description='x', eligibility='x', requirements=[])

        self.office = PartnerOffice.objects.create(name='DOST Region VIII')
        self.office.scholarships.add(self.dost)
        self.account = User.objects.create_user(
            username='dost@bipsu.edu.ph', email='dost@bipsu.edu.ph',
            password='pw', role='partner')
        self.account.partner_office = self.office
        self.account.save()

        self.c = Client()
        self.assertTrue(self.c.login(email='dost@bipsu.edu.ph', password='pw'))

    def _row(self, stype='DOST', **kw):
        return ImportedScholar.objects.create(
            scholarship_type=stype, term_label='26-1',
            last_name=kw.pop('last_name', 'Santos'),
            first_name=kw.pop('first_name', 'Maria'), **kw)

    def _post(self, **body):
        data = {'type': 'DOST', 'sy': '26-1'}
        data.update(body)
        return self.c.post(self.URL, data)


class AddingAScholarTest(PartnerScholarFixtures, TestCase):
    def test_a_partner_adds_to_its_own_list(self):
        r = self._post(action='add', last_name='Villanueva', first_name='Ana',
                       course='BSCS', year_level='3', gwa='1.35',
                       student_id='2023-0451', award_number='2026-DOST-00194')
        self.assertEqual(r.status_code, 302)

        row = ImportedScholar.objects.get()
        self.assertEqual(row.scholarship_type, 'DOST')
        self.assertEqual(row.term_label, '26-1')
        self.assertEqual((row.last_name, row.first_name), ('Villanueva', 'Ana'))
        self.assertEqual((row.year_level, row.gwa), (3, 1.35))

    def test_the_row_says_who_put_it_there(self):
        self._post(action='add', last_name='Villanueva', first_name='Ana')
        self.assertEqual(ImportedScholar.objects.get().imported_from,
                         'Added by DOST Region VIII')

    def test_the_office_can_see_what_the_partner_did(self):
        self._post(action='add', last_name='Villanueva', first_name='Ana')
        self.assertTrue(ActivityLog.objects.filter(
            action__contains='DOST Region VIII added the DOST scholar Ana Villanueva'
        ).exists())

    def test_a_row_with_no_name_at_all_is_refused(self):
        r = self._post(action='add', course='BSCS')
        self.assertIn('first%20or%20a%20last%20name',
                      r['Location'].replace('+', '%20'))
        self.assertFalse(ImportedScholar.objects.exists())

    def test_one_name_is_enough(self):
        self._post(action='add', last_name='Villanueva')
        self.assertEqual(ImportedScholar.objects.count(), 1)

    def test_a_year_level_that_is_not_one_is_refused(self):
        for bad in ('third', '0', '99'):
            with self.subTest(year=bad):
                r = self._post(action='add', last_name='X', year_level=bad)
                self.assertIn('error=', r['Location'])
        self.assertFalse(ImportedScholar.objects.exists())

    def test_a_gwa_that_is_not_a_number_is_refused(self):
        r = self._post(action='add', last_name='X', gwa='very good')
        self.assertIn('error=', r['Location'])
        self.assertFalse(ImportedScholar.objects.exists())

    def test_blank_numbers_land_on_zero_rather_than_refusing(self):
        self._post(action='add', last_name='Villanueva', year_level='', gwa='')
        row = ImportedScholar.objects.get()
        self.assertEqual((row.year_level, row.gwa), (0, 0.0))


class EditingAndDeletingTest(PartnerScholarFixtures, TestCase):
    def test_a_partner_corrects_its_own_row(self):
        row = self._row(course='BSCS', year_level=3)
        self._post(action='edit', scholar_id=row.pk,
                   last_name='Santos', first_name='Maria',
                   course='BSIT', year_level='4')
        row.refresh_from_db()
        self.assertEqual((row.course, row.year_level), ('BSIT', 4))

    def test_an_edit_cannot_move_a_scholar_to_another_programme(self):
        row = self._row()
        self._post(action='edit', scholar_id=row.pk, last_name='Santos',
                   scholarship_type='CHED', term_label='25-2')
        row.refresh_from_db()
        self.assertEqual(row.scholarship_type, 'DOST')
        self.assertEqual(row.term_label, '26-1')

    def test_a_partner_removes_its_own_row(self):
        row = self._row()
        self._post(action='delete', scholar_id=row.pk)
        self.assertFalse(ImportedScholar.objects.filter(pk=row.pk).exists())

    def test_both_are_logged(self):
        row = self._row()
        self._post(action='edit', scholar_id=row.pk, last_name='Santos',
                   first_name='Maria')
        self._post(action='delete', scholar_id=row.pk)
        actions = list(ActivityLog.objects.values_list('action', flat=True))
        self.assertTrue(any('edited the DOST scholar' in a for a in actions))
        self.assertTrue(any('deleted the DOST scholar' in a for a in actions))

    def test_an_unknown_action_changes_nothing(self):
        row = self._row()
        r = self._post(action='ransack', scholar_id=row.pk)
        self.assertIn('error=', r['Location'])
        self.assertTrue(ImportedScholar.objects.filter(pk=row.pk).exists())

    def test_a_get_does_nothing(self):
        row = self._row()
        self.assertEqual(self.c.get(self.URL).status_code, 302)
        self.assertTrue(ImportedScholar.objects.filter(pk=row.pk).exists())


class TheThreeLinesTest(PartnerScholarFixtures, TestCase):
    def test_another_programmes_name_is_refused(self):
        r = self._post(action='add', type='CHED', last_name='Sneaky')
        self.assertIn('not+one+this+account+can+read',
                      r['Location'].replace('%20', '+'))
        self.assertFalse(ImportedScholar.objects.exists())

    def test_another_programmes_row_is_not_reachable(self):
        theirs = self._row(stype='CHED', last_name='Notyours')
        r = self._post(action='delete', scholar_id=theirs.pk)
        self.assertIn('error=', r['Location'])
        self.assertTrue(ImportedScholar.objects.filter(pk=theirs.pk).exists())

    def test_another_programmes_row_cannot_be_edited_either(self):
        theirs = self._row(stype='CHED', last_name='Notyours')
        self._post(action='edit', scholar_id=theirs.pk, last_name='Rewritten')
        theirs.refresh_from_db()
        self.assertEqual(theirs.last_name, 'Notyours')

    def test_a_row_claimed_by_a_student_is_the_offices(self):
        user = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            first_name='Juan', last_name='Cruz', role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id='2024-0001', course='BSCS', year_level=2)
        row = self._row(claimed_by=profile, last_name='Cruz')

        self._post(action='edit', scholar_id=row.pk, last_name='Rewritten')
        row.refresh_from_db()
        self.assertEqual(row.last_name, 'Cruz')

        self._post(action='delete', scholar_id=row.pk)
        self.assertTrue(ImportedScholar.objects.filter(pk=row.pk).exists())

    def test_an_award_row_is_not_an_imported_row(self):
        user = User.objects.create_user(
            username='a@bipsu.edu.ph', email='a@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Reyes', role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id='2024-0002', course='BSCS', year_level=2)
        award = Application.objects.create(
            student=profile, scholarship=self.dost, status='Approved',
            term_label='26-1')

        self._post(action='delete', scholar_id=award.pk)
        self.assertTrue(Application.objects.filter(pk=award.pk).exists())

    def test_the_endpoint_is_closed_to_everyone_else(self):
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            role='vpsea')
        office = Client()
        self.assertTrue(office.login(email='v@bipsu.edu.ph', password='pw'))
        for client in (office, Client()):
            r = client.post(self.URL, {'action': 'add', 'type': 'DOST',
                                       'sy': '26-1', 'last_name': 'X'})
            self.assertEqual(r.status_code, 302)
            self.assertNotIn('/partner/', r['Location'])
        self.assertFalse(ImportedScholar.objects.exists())

    def test_a_suspended_partner_cannot_reach_it(self):
        PartnerOffice.objects.filter(pk=self.office.pk).update(is_active=False)
        self._post(action='add', last_name='X')
        self.assertFalse(ImportedScholar.objects.exists())


class ThePageShowsWhatIsEditableTest(PartnerScholarFixtures, TestCase):
    def test_an_imported_row_carries_both_buttons(self):
        self._row(last_name='Santos', first_name='Maria')
        html = self.c.get(f'{self.PAGE}?type=DOST&sy=26-1').content.decode()
        self.assertIn('data-scholar-edit', html)
        self.assertIn('name="action" value="delete"', html)

    def test_an_award_row_carries_neither(self):
        user = User.objects.create_user(
            username='a@bipsu.edu.ph', email='a@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Reyes', role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id='2024-0002', course='BSCS', year_level=2)
        Application.objects.create(student=profile, scholarship=self.dost,
                                   status='Approved', term_label='26-1')

        html = self.c.get(f'{self.PAGE}?type=DOST&sy=26-1').content.decode()
        self.assertIn('BiPSU account', html)
        self.assertNotIn('data-scholar-edit', html)


class TheColumnPickerIsADialogNowTest(PartnerScholarFixtures, TestCase):
    def test_the_card_is_gone(self):
        html = self.c.get(f'{self.PAGE}?type=DOST').content.decode()
        self.assertNotIn('col-panel', html)
        self.assertNotIn('Columns — lay this table out your own way', html)

    def test_the_picker_moved_into_a_dialog_off_the_action_row(self):
        html = self.c.get(f'{self.PAGE}?type=DOST').content.decode()
        self.assertIn('data-preview-open="columnsModal"', html)
        self.assertIn('id="columnsModal"', html)
        self.assertIn('id="columnPicker"', html)
        self.assertIn('action="/partner/columns/"', html)

    def test_saving_a_layout_still_works_from_the_dialog(self):
        from api.models import PartnerTableColumns

        self.c.post('/partner/columns/',
                    {'type': 'DOST', 'table_columns': ['last_name', 'first_name']})
        saved = PartnerTableColumns.objects.get(office=self.office,
                                                scholarship=self.dost)
        self.assertEqual(saved.table_columns, ['last_name', 'first_name'])
