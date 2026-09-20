"""The import runs after the office has been let go of.

A workbook big enough to matter took longer to read than gunicorn's 120-second
timeout, so the request doing the reading was killed part-way and the office
was shown nothing at all. The reading now happens on the pool in ``api/jobs.py``
and the archive page follows the ``BackgroundJob`` row.

Every other import case runs with ``BACKGROUND_JOBS_SYNCHRONOUS`` on, which is
what lets them assert against a finished import. These turn it off, so they are
the only ones that see what the office actually sees.
"""

from io import BytesIO
from urllib.parse import parse_qs, urlparse

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TransactionTestCase, override_settings

from api.fixtures_threads import ThreadedSqliteMixin
from api.models import (
    BackgroundJob, ImportedScholar, Scholarship, SystemSettings, User,
)

HEADINGS = ['No.', 'Award Number', 'Last Name', 'First Name', 'Middle Name',
            'Sex', 'Brgy./St.', 'Municipality', 'Province', 'Congress District',
            'Course', 'Yr.', 'Scholarship Program']


def a_sheet(count=2):
    """A DOST scholar list, as the office uploads one."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(HEADINGS)
    for n in range(1, count + 1):
        sheet.append([n, f'AW-{n}', f'Surname{n}', 'Maria', 'R', 'F',
                      'Poblacion', 'Naval', 'Biliran', '1st', 'BSCS', '2',
                      'DOST'])
    buffer = BytesIO()
    book.save(buffer)
    return SimpleUploadedFile(
        'dost.xlsx', buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument'
                     '.spreadsheetml.sheet')


@override_settings(BACKGROUND_JOBS_SYNCHRONOUS=False)
class ImportRunsInTheBackgroundTest(ThreadedSqliteMixin, TransactionTestCase):
    """``TransactionTestCase``: the pool thread is outside the case's transaction."""

    def setUp(self):
        super().setUp()
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        Scholarship.objects.create(
            name='DOST Scholarship', type='DOST', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def tearDown(self):
        self._settle()

    def _settle(self):
        """Wait for the import to finish, without holding it up."""
        return self.settle()

    def _upload(self, count=2):
        return self.c.post('/vpsea/archives/import/', {
            'type': 'DOST', 'rollover_label': '26-1', 'file': a_sheet(count)})

    def _job_from(self, response):
        query = parse_qs(urlparse(response['Location']).query)
        return BackgroundJob.objects.get(pk=query['import_job'][0])

    def test_the_office_is_sent_on_with_a_job_rather_than_a_count(self):
        job = self._job_from(self._upload())
        self.assertEqual(job.kind, 'archive-import')
        self.assertEqual(job.started_by.email, 'v@bipsu.edu.ph')

    def test_the_spreadsheet_is_read_after_the_request_has_ended(self):
        response = self._upload(count=3)
        self.assertTrue(self._settle(), 'the import never finished')
        job = self._job_from(response)
        self.assertEqual(job.status, BackgroundJob.DONE)
        self.assertEqual(job.outcome.get('created'), 3)
        self.assertEqual(ImportedScholar.objects.count(), 3)

    def test_the_upload_survives_the_request_that_carried_it(self):
        self._upload()
        self.assertTrue(self._settle())
        self.assertEqual(
            sorted(ImportedScholar.objects.values_list('imported_from',
                                                       flat=True)),
            ['dost.xlsx', 'dost.xlsx'],
            'the job lost the name of the file it was reading')

    def test_the_page_says_the_import_is_still_going_and_where_to_ask(self):
        response = self._upload()
        job = self._job_from(response)
        job.status, job.outcome = BackgroundJob.RUNNING, {}
        job.save(update_fields=['status', 'outcome'])

        html = self.c.get(response['Location']).content.decode()
        self.assertIn('Reading the spreadsheet', html)
        self.assertIn(f'/vpsea/archives/import/{job.pk}/status/', html)
        self._settle()

    def test_the_page_shows_the_count_once_the_job_has_finished(self):
        response = self._upload(count=2)
        self.assertTrue(self._settle())
        html = self.c.get(response['Location']).content.decode()
        self.assertIn('Successfully imported 2 records.', html)
        self.assertNotIn('Reading the spreadsheet', html)

    def test_the_status_endpoint_reports_the_job_it_is_asked_about(self):
        response = self._upload()
        job = self._job_from(response)
        self.assertTrue(self._settle())

        answer = self.c.get(f'/vpsea/archives/import/{job.pk}/status/').json()
        self.assertTrue(answer['finished'])
        self.assertEqual(answer['status'], BackgroundJob.DONE)

    def test_the_status_endpoint_is_not_open_to_anyone_else(self):
        job = self._job_from(self._upload())
        self._settle()
        self.c.logout()
        refused = self.c.get(f'/vpsea/archives/import/{job.pk}/status/')
        self.assertNotEqual(
            refused.status_code, 200,
            'a signed-out caller could read the office import queue')

    def test_an_import_lost_to_a_restart_says_so_instead_of_spinning(self):
        from datetime import timedelta

        from django.utils import timezone

        response = self._upload()
        job = self._job_from(response)
        self.assertTrue(self._settle())

        BackgroundJob.objects.filter(pk=job.pk).update(
            status=BackgroundJob.RUNNING, finished_at=None,
            started_at=timezone.now() - timedelta(hours=2))

        html = self.c.get(response['Location']).content.decode()
        self.assertIn('interrupted before it finished', html)
        self.assertNotIn('Reading the spreadsheet', html,
                         'the page went on waiting for a job nobody was running')

    def test_a_job_id_that_names_nothing_is_ignored_rather_than_crashing(self):
        page = self.c.get('/vpsea/archives/', {'type': 'DOST',
                                               'import_job': 'not-a-number'})
        self.assertEqual(page.status_code, 200)
