from io import BytesIO

import openpyxl
from django.core.files.base import ContentFile, File
from django.core.files.storage import Storage
from django.test import Client, TestCase, override_settings

from api.models import (
    Scholarship, ScholarListImport, SystemSettings, User,
)


class PathlessStorage(Storage):
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

    def test_course_counts_come_off_a_sheet_with_no_local_path(self):
        self.rollover('CHED', '25-2',
                      [['Cruz', 'BSCE'], ['Lim', 'BSCE'], ['Reyes', 'BSIT']],
                      ['Name', 'Course'])
        courses = {row['course']: row['scholars']
                   for row in self.page('25-2').context['course_dist']}
        self.assertEqual(courses, {'BSCE': 2, 'BSIT': 1})

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
        with self.assertLogs('api', level='ERROR'):
            self.assertEqual(self.page('25-2').context['course_dist'], [])
