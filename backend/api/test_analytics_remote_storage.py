"""Analytics when uploads are not on the local disk.

The deployed site keeps uploads in Supabase Storage, and that backend has no
``path()`` — Django's base Storage raises NotImplementedError for it, because
there is no local file to name. The rollover sheets a past semester is read
back from were being opened with ``openpyxl.load_workbook(field.excel_file.path)``,
so every one of those reads raised on its first line, the ``except Exception``
around it returned an empty tally, and the analytics page drew empty charts.

Locally, on a FileSystemStorage, the same code worked perfectly. That is the
whole shape of the bug: nothing to see in development, nothing on the page in
production. These tests run the rollover reads against a storage backend with
no ``path()``, which is what the deployed one is.
"""
from io import BytesIO

import openpyxl
from django.core.files.base import ContentFile, File
from django.core.files.storage import Storage
from django.test import Client, TestCase, override_settings

from api.models import (
    Scholarship, ScholarListImport, SystemSettings, User,
)


class PathlessStorage(Storage):
    """A bucket, in the only way that matters here: bytes in, bytes out, no path.

    ``path()`` is deliberately left to inherit the base Storage implementation
    — the one that raises NotImplementedError. That inheritance IS the
    condition under test, and it is the same one django-storages' S3Storage
    sits under, so anything reaching for a filesystem path fails here exactly
    as it does on Supabase.
    """

    _files = {}

    def _open(self, name, mode='rb'):
        return File(BytesIO(self._files[name]), name)

    def _save(self, name, content):
        content.seek(0)
        self._files[name] = content.read()
        return name

    def delete(self, name):
        self._files.pop(name, None)

    def exists(self, name):
        return name in self._files

    def listdir(self, path):
        return [], list(self._files)

    def size(self, name):
        return len(self._files[name])

    def url(self, name):
        return f'/media/{name}'


def _sheet(rows, headers):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


@override_settings(STORAGES={
    'default': {'BACKEND': 'api.test_analytics_remote_storage.PathlessStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class RolloverOnRemoteStorageTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        for stype in ('Academic', 'CHED'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype, category='application',
                description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def rollover(self, stype, label, rows, headers):
        record = ScholarListImport.objects.create(
            scholarship_type=stype, term_label=label, scholar_count=len(rows))
        record.excel_file.save(f'{stype}_{label}.xlsx',
                               ContentFile(_sheet(rows, headers)), save=True)
        return record

    def page(self, label):
        r = self.c.get('/vpsea/analytics/', {'sy': label})
        self.assertEqual(r.status_code, 200)
        return r

    # ── the reads that were raising ─────────────────────────────────────────

    def test_course_counts_come_off_a_sheet_with_no_local_path(self):
        self.rollover('CHED', '25-2',
                      [['Cruz', 'BSCE'], ['Lim', 'BSCE'], ['Reyes', 'BSIT']],
                      ['Name', 'Course'])
        courses = {row['course']: row['scholars']
                   for row in self.page('25-2').context['course_dist']}
        self.assertEqual(courses, {'BSCE': 2, 'BSIT': 1})

    def test_the_school_tally_is_built_from_that_same_sheet(self):
        self.rollover('CHED', '25-2', [['Cruz', 'BSCE'], ['Lim', 'BSCE']],
                      ['Name', 'Course'])
        schools = {row['school']: row['scholars']
                   for row in self.page('25-2').context['school_dist']}
        self.assertEqual(sum(schools.values()), 2)

    def test_gwa_bands_come_off_a_sheet_with_no_local_path(self):
        self.rollover('Academic', '25-2',
                      [['Cruz', 1.1], ['Lim', 1.4], ['Reyes', 1.45]],
                      ['Name', 'GWA'])
        bands = {b['range']: b['count']
                 for b in self.page('25-2').context['gpa_ranges']}
        self.assertEqual(bands['1.00-1.25'], 1)
        self.assertEqual(bands['1.26-1.50'], 2)

    def test_an_unreadable_sheet_still_leaves_the_page_standing(self):
        record = ScholarListImport.objects.create(
            scholarship_type='CHED', term_label='25-2', scholar_count=1)
        record.excel_file.save('CHED_25-2.xlsx', ContentFile(b'not a workbook'),
                               save=True)
        with self.assertLogs('api.student_views', level='ERROR'):
            self.assertEqual(self.page('25-2').context['course_dist'], [])
