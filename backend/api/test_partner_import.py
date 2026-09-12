"""A partner uploading a whole term of its own list at once.

The office has had Upload Excel on Scholarship Archives since the beginning. A
funder adding three hundred scholars one dialog at a time was the same work done
three hundred times, so the button is on the partner's Scholars page too — and
the two read a spreadsheet through the same function, so a column can never mean
one thing to the office and another to the funder who sent the file.

What differs is what an import is allowed to replace, and that is the whole of
what these tests are about. The office's import clears the term outright. A
partner's clears **only the rows that are its own**: a scholar the office has
already matched to a BiPSU student account survives a sheet that does not
mention them, because that match was a decision somebody made after checking,
and a spreadsheet arriving afterwards must not be able to quietly undo it.

The two lines a partner cannot cross elsewhere hold here as well — its own
programmes only, and never an award row — and for the same reason: they are
part of *finding* what to delete rather than a check remembered afterwards.
"""
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from openpyxl import Workbook

from api.models import (
    ActivityLog, ImportedScholar, PartnerOffice, Scholarship, ScholarListImport,
    StudentProfile, SystemSettings, User,
)

# The DOST sheet, as COLUMN_MAPS reads it: a row number, then the award number,
# then the name. Everything past Province is left off on purpose — a funder's
# own export is never exactly the office's template, and a short row is the
# ordinary case rather than the broken one.
HEADER = ['No.', 'Award Number', 'Last Name', 'First Name', 'Middle Name',
          'Sex', 'Brgy./St.', 'Municipality', 'Province']


def sheet(rows):
    """One .xlsx upload carrying these scholars."""
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    for index, (award, last, first) in enumerate(rows, start=1):
        ws.append([index, award, last, first, '', 'F', 'Poblacion', 'Naval',
                   'Biliran'])
    buf = BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(
        'dost-26-1.xlsx', buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


class PartnerImportFixtures:
    """One partner that funds DOST, and a CHED list it was never given."""

    URL = '/partner/archives/import/'

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

    def upload(self, rows, stype='DOST', term='26-1'):
        return self.c.post(self.URL, {
            'type': stype, 'rollover_label': term, 'file': sheet(rows)})

    def names(self, stype='DOST', term='26-1'):
        return sorted(ImportedScholar.objects
                      .filter(scholarship_type=stype, term_label=term)
                      .values_list('last_name', flat=True))


class ImportingATermTest(PartnerImportFixtures, TestCase):

    def test_a_sheet_becomes_rows_on_the_partners_own_list(self):
        self.upload([('AW-1', 'Santos', 'Maria'), ('AW-2', 'Cruz', 'Jose')])
        self.assertEqual(self.names(), ['Cruz', 'Santos'])

    def test_the_rows_land_in_the_term_the_upload_named(self):
        self.upload([('AW-1', 'Santos', 'Maria')], term='25-2')
        self.assertEqual(self.names(term='25-2'), ['Santos'])
        self.assertEqual(self.names(term='26-1'), [])

    def test_the_office_can_tell_who_sent_the_file(self):
        """The archive's own column says so, without a column being added."""
        self.upload([('AW-1', 'Santos', 'Maria')])
        row = ImportedScholar.objects.get(last_name='Santos')
        self.assertIn('DOST Region VIII', row.imported_from)
        self.assertIn('dost-26-1.xlsx', row.imported_from)

    def test_the_term_shows_up_in_download_excel_afterwards(self):
        self.upload([('AW-1', 'Santos', 'Maria'), ('AW-2', 'Cruz', 'Jose')])
        saved = ScholarListImport.objects.get(scholarship_type='DOST',
                                              term_label='26-1')
        self.assertEqual(saved.scholar_count, 2)
        self.assertEqual(saved.imported_by, self.account)

    def test_importing_the_same_term_twice_leaves_one_history_row(self):
        self.upload([('AW-1', 'Santos', 'Maria')])
        self.upload([('AW-1', 'Santos', 'Maria'), ('AW-2', 'Cruz', 'Jose')])
        saved = ScholarListImport.objects.filter(scholarship_type='DOST',
                                                 term_label='26-1')
        self.assertEqual(saved.count(), 1)
        self.assertEqual(saved.first().scholar_count, 2)

    def test_it_is_written_down_who_imported_what(self):
        self.upload([('AW-1', 'Santos', 'Maria')])
        log = ActivityLog.objects.latest('id').action
        self.assertIn('DOST Region VIII', log)
        self.assertIn('dost-26-1.xlsx', log)


class WhatAnImportReplacesTest(PartnerImportFixtures, TestCase):

    def _imported(self, last_name, claimed_by=None, term='26-1'):
        return ImportedScholar.objects.create(
            scholarship_type='DOST', term_label=term, last_name=last_name,
            first_name='Maria', claimed_by=claimed_by)

    def _student(self):
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
            password='pw', role='student', first_name='Ana', last_name='Lim')
        return StudentProfile.objects.create(
            user=user, student_id='2022-00111', course='BSCS', year_level=2)

    def test_the_partners_own_rows_for_that_term_are_replaced(self):
        self._imported('Dela Cruz')
        self.upload([('AW-1', 'Santos', 'Maria')])
        self.assertEqual(self.names(), ['Santos'])

    def test_a_claimed_row_survives_a_sheet_that_forgot_it(self):
        """The office matched this scholar to a student. A file cannot unmatch.

        The one case this whole endpoint is careful about: the office's import
        clears the term outright, and doing that here would delete a row the
        partner is not allowed to so much as edit.
        """
        self._imported('Matched', claimed_by=self._student())
        self.upload([('AW-1', 'Santos', 'Maria')])
        self.assertEqual(self.names(), ['Matched', 'Santos'])

    def test_another_term_is_left_alone(self):
        self._imported('LastYear', term='25-2')
        self.upload([('AW-1', 'Santos', 'Maria')])
        self.assertEqual(self.names(term='25-2'), ['LastYear'])

    def test_another_programmes_list_is_left_alone(self):
        ImportedScholar.objects.create(
            scholarship_type='CHED', term_label='26-1', last_name='Reyes',
            first_name='Ana')
        self.upload([('AW-1', 'Santos', 'Maria')])
        self.assertEqual(self.names(stype='CHED'), ['Reyes'])


class WhatAPartnerMayNotImportTest(PartnerImportFixtures, TestCase):

    def test_a_programme_it_was_never_given_is_refused(self):
        ImportedScholar.objects.create(
            scholarship_type='CHED', term_label='26-1', last_name='Reyes',
            first_name='Ana')
        response = self.upload([('AW-1', 'Santos', 'Maria')], stype='CHED')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.names(stype='CHED'), ['Reyes'])

    def test_a_file_is_required(self):
        response = self.c.post(self.URL, {'type': 'DOST', 'rollover_label': '26-1'})
        self.assertIn('import_error', response['Location'])
        self.assertEqual(self.names(), [])

    def test_a_term_is_required(self):
        response = self.c.post(self.URL, {
            'type': 'DOST', 'rollover_label': '', 'file': sheet([('A', 'B', 'C')])})
        self.assertIn('import_error', response['Location'])
        self.assertEqual(ImportedScholar.objects.count(), 0)

    def test_a_file_that_is_not_a_workbook_destroys_nothing(self):
        """The parse happens before the delete, which is the point.

        The office's import had this bug once — the term was cleared, then the
        sheet was read, so a file openpyxl choked on emptied the archive and put
        nothing back.
        """
        ImportedScholar.objects.create(
            scholarship_type='DOST', term_label='26-1', last_name='Existing',
            first_name='Maria')
        response = self.c.post(self.URL, {
            'type': 'DOST', 'rollover_label': '26-1',
            'file': SimpleUploadedFile('notes.xlsx', b'not a workbook at all',
                                       content_type='application/vnd.ms-excel')})
        self.assertIn('import_error', response['Location'])
        self.assertEqual(self.names(), ['Existing'])

    def test_a_signed_out_visitor_gets_nowhere(self):
        self.c.logout()
        response = self.upload([('AW-1', 'Santos', 'Maria')])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImportedScholar.objects.count(), 0)

    def test_a_get_imports_nothing(self):
        response = self.c.get(self.URL)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImportedScholar.objects.count(), 0)


class TheOfficeSideOfTheSharedParserTest(TestCase):
    """The SDSO's own Upload Excel, which reads the sheet through the same code.

    It had no test of its own. Adding the partner's import moved the loop that
    reads a workbook into `_scholars_from_sheet`, and a shared function wants
    its other caller held down too — otherwise the next change to the column
    contract is made against one of the two pages and discovered on the other.

    The office's import is the one that clears a term outright, claimed rows
    included; that is its prerogative and this says so.
    """

    URL = '/vpsea/archives/import/'

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        Scholarship.objects.create(
            name='DOST Scholarship', type='DOST', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='pw', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='sdso@bipsu.edu.ph', password='pw'))

    def test_the_office_import_still_reads_a_sheet(self):
        self.c.post(self.URL, {
            'type': 'DOST', 'rollover_label': '26-1',
            'file': sheet([('AW-1', 'Santos', 'Maria'), ('AW-2', 'Cruz', 'Jose')])})
        rows = ImportedScholar.objects.filter(scholarship_type='DOST',
                                              term_label='26-1')
        self.assertEqual(sorted(rows.values_list('last_name', flat=True)),
                         ['Cruz', 'Santos'])
        # The column past the row number, which is where a DOST sheet differs
        # from a CoScho one — the half of the contract worth holding down.
        self.assertEqual(rows.get(last_name='Santos').award_number, 'AW-1')
        self.assertEqual(
            ScholarListImport.objects.get(scholarship_type='DOST',
                                          term_label='26-1').scholar_count, 2)

    def test_the_office_import_clears_the_term_it_replaces(self):
        ImportedScholar.objects.create(
            scholarship_type='DOST', term_label='26-1', last_name='Gone',
            first_name='Maria')
        self.c.post(self.URL, {
            'type': 'DOST', 'rollover_label': '26-1',
            'file': sheet([('AW-1', 'Santos', 'Maria')])})
        self.assertEqual(
            sorted(ImportedScholar.objects.filter(term_label='26-1')
                   .values_list('last_name', flat=True)), ['Santos'])
