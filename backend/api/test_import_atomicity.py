"""The spreadsheet import either files completely or files nothing.

Two defects are pinned here. The first: ``transaction.atomic()`` wrapped only
the scholar rows, and the parent ``ScholarListImport`` — which carries the
source file and the count — was written after it. A failure between the two
left scholar rows committed with no record of where they came from, while the
office was told the import had failed. The second: the exception's own text
was pushed into the redirect URL, putting database errors, file paths and S3
endpoint details into the query string, browser history and server logs.

The import has since moved onto the background pool, so a refusal reaches the
office through a ``BackgroundJob`` row rather than the query string. That is
one more place the exception text could surface, so both are checked.
"""

from io import BytesIO
from unittest.mock import patch

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from urllib.parse import parse_qs, urlparse

from api.models import (
    BackgroundJob, ImportedScholar, Scholarship, ScholarListImport,
    SystemSettings, User,
)

SECRET_LOOKING_TEXT = (
    'FATAL: password authentication failed for user "srms" at '
    'https://abcdefgh.supabase.co/storage/v1/s3 (/srv/app/media/rollovers)')


CHED_HEADINGS = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME',
                 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.',
                 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']


def a_ched_scholar(number, award_number, last_name, first_name='Maria'):
    """One row in the CHED layout the office's sheets use."""
    return [number, award_number, last_name, first_name, 'R', 'F',
            'Poblacion', 'Naval', 'Biliran', 'Lone District', 'BSCS', 2,
            'CHED Merit']


def a_scholar_sheet(rows):
    """A scholar spreadsheet in the CHED layout, as the office uploads one."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(CHED_HEADINGS)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    book.save(buffer)
    return SimpleUploadedFile(
        'scholars.xlsx', buffer.getvalue(),
        content_type=('application/vnd.openxmlformats-officedocument'
                      '.spreadsheetml.sheet'))


class ArchiveImportTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        Scholarship.objects.create(
            name='CHED Merit', type='CHED', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea')
        self.client = Client()
        self.assertTrue(self.client.login(
            email='vpsea@bipsu.edu.ph', password='pw'))

    def _import(self, rows=None):
        """Post a scholar list, as the archive page does."""
        rows = rows if rows is not None else [
            a_ched_scholar(1, 'CHED-2026-0001', 'Santos'),
            a_ched_scholar(2, 'CHED-2026-0002', 'Cruz', 'Jose'),
        ]
        return self.client.post('/vpsea/archives/import/', {
            'type': 'CHED',
            'rollover_label': '26-1',
            'file': a_scholar_sheet(rows),
        })

    def _error_from(self, response):
        """What the office is told, wherever the refusal was written.

        A refusal the view can make on its own -- no file, no rollover name
        -- is still in the query string. One only the import can make now
        lands on the job row the redirect names.
        """
        query = parse_qs(urlparse(response['Location']).query)
        direct = (query.get('import_error') or [''])[0]
        if direct:
            return direct
        job_id = (query.get('import_job') or [''])[0]
        return BackgroundJob.objects.get(pk=job_id).detail if job_id else ''

    def test_a_good_sheet_files_the_scholars_and_the_parent_record(self):
        self._import()
        self.assertEqual(ImportedScholar.objects.count(), 2)
        self.assertEqual(ScholarListImport.objects.count(), 1)
        self.assertEqual(ScholarListImport.objects.get().scholar_count, 2)

    def test_a_failure_filing_the_parent_leaves_no_orphan_scholars(self):
        with patch.object(ScholarListImport, 'save',
                          side_effect=RuntimeError(SECRET_LOOKING_TEXT)):
            response = self._import()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ImportedScholar.objects.count(), 0,
            'scholar rows were committed although the office was told the '
            'import failed')
        self.assertEqual(ScholarListImport.objects.count(), 0)

    def test_a_failure_does_not_destroy_the_term_it_was_replacing(self):
        self._import()
        self.assertEqual(ImportedScholar.objects.count(), 2)

        with patch.object(ScholarListImport, 'save',
                          side_effect=RuntimeError('nope')):
            self.client.post('/vpsea/archives/import/', {
                'type': 'CHED',
                'rollover_label': '26-2',
                'file': a_scholar_sheet([
                    a_ched_scholar(1, 'CHED-2026-0003', 'Reyes', 'Ana')]),
            })

        self.assertEqual(
            ImportedScholar.objects.filter(term_label='26-1').count(), 2,
            'a failed import for one term deleted another term')

    def test_the_exception_text_never_reaches_the_office(self):
        with patch.object(ScholarListImport, 'save',
                          side_effect=RuntimeError(SECRET_LOOKING_TEXT)):
            response = self._import()

        told = response['Location'] + ' ' + self._error_from(response)
        for leaked in ('password authentication', 'supabase.co', '/srv/app',
                       'RuntimeError'):
            with self.subTest(leaked=leaked):
                self.assertNotIn(leaked, told)

    def test_the_office_is_still_told_plainly_that_nothing_was_saved(self):
        with patch.object(ScholarListImport, 'save',
                          side_effect=RuntimeError(SECRET_LOOKING_TEXT)):
            response = self._import()
        self.assertIn('Nothing was saved', self._error_from(response))

    def test_the_failure_is_written_to_the_log_rather_than_swallowed(self):
        with (patch.object(ScholarListImport, 'save',
                           side_effect=RuntimeError(SECRET_LOOKING_TEXT)),
              self.assertLogs('api.views_archives', level='ERROR') as logged):
            self._import()
        self.assertIn(SECRET_LOOKING_TEXT, '\n'.join(logged.output))

    def test_a_sheet_repeating_one_award_number_is_refused_whole(self):
        response = self._import([
            a_ched_scholar(1, 'CHED-2026-0007', 'Santos'),
            a_ched_scholar(2, 'CHED-2026-0007', 'Cruz', 'Jose'),
        ])
        self.assertEqual(ImportedScholar.objects.count(), 0)
        self.assertEqual(ScholarListImport.objects.count(), 0)
        self.assertIn('same award number twice', self._error_from(response))


class ReportErrorTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea')
        self.client = Client()
        self.client.login(email='vpsea@bipsu.edu.ph', password='pw')

    def test_a_missing_template_does_not_put_the_server_path_in_the_url(self):
        from api import masterlist_report

        missing = FileNotFoundError(
            'The masterlist template is missing at '
            '/srv/app/api/templates/docx/masterlist.docx.')
        with patch.object(masterlist_report, 'build_document',
                          side_effect=missing):
            response = self.client.get('/vpsea/reports/download/')

        self.assertEqual(response.status_code, 302)
        self.assertNotIn('/srv/app', response['Location'])
        query = parse_qs(urlparse(response['Location']).query)
        self.assertIn('missing on the server', (query.get('error') or [''])[0])
