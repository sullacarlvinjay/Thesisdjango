"""The TDP masterlist — the same treatment TES gets on the UniFAST Reports page.

Its own summary box, its own download and its own preview frame, all scoped to
the school year picked in the toolbar. What is guarded here is that the two
programmes stay separated: a TDP report that quietly carried TES grantees, or a
combined masterlist that lost one of them, is the failure worth catching.
"""
import openpyxl
from io import BytesIO
from unittest import mock

from django.test import TestCase, Client

from api.models import (
    User, StudentProfile, Scholarship, Application, SystemSettings,
)
from api.test_support import pdf_text


def sheet_text(content, sheet):
    ws = openpyxl.load_workbook(BytesIO(content))[sheet]
    return '\n'.join(
        str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)


class TDPReportTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        for stype, name in (('TDP', 'Tulong Dunong'), ('TES', 'TES'),
                            ('Academic', 'Academic Scholarship')):
            Scholarship.objects.create(
                name=name, type=stype, category='application',
                description='x', eligibility='x', requirements=[],
            )
        User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
            password='pw', role='unifast',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='unifast@bipsu.edu.ph', password='pw'))

    def _scholar(self, stype, last, gender, sid, school_year='2026-2027'):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph',
            password='pw', first_name='Test', last_name=last, role='student',
        )
        p = StudentProfile.objects.create(
            user=u, student_id=sid, course='BSCS', year_level=2, gender=gender,
            barangay='Poblacion', municipality='Naval', province='Biliran',
        )
        return Application.objects.create(
            student=p, scholarship=Scholarship.objects.get(type=stype),
            status='Approved', school_year=school_year, semester='1st Semester',
            award_number=f'AW-{sid}',
        )

    # ── The box ─────────────────────────────────────────────────────────────

    def test_reports_page_counts_tdp_scholars_by_gender(self):
        self._scholar('TDP', 'Cruz', 'Female', 'S1')
        self._scholar('TDP', 'Bautista', 'Male', 'S2')
        self._scholar('TDP', 'Aquino', 'Male', 'S3')
        self._scholar('TES', 'Reyes', 'Male', 'S4')

        r = self.c.get('/unifast/reports/')
        self.assertEqual(r.context['tdp_total'], 3)
        self.assertEqual(r.context['tdp_female'], 1)
        self.assertEqual(r.context['tdp_male'], 2)
        self.assertContains(r, 'TDP scholars')

    def test_the_tdp_box_follows_the_school_year(self):
        self._scholar('TDP', 'Cruz', 'Female', 'S1', school_year='2026-2027')
        self._scholar('TDP', 'Reyes', 'Male', 'S2', school_year='2025-2026')

        r = self.c.get('/unifast/reports/?sy=2025-2026')
        self.assertEqual(r.context['tdp_total'], 1)
        self.assertEqual(r.context['tdp_male'], 1)
        self.assertEqual(r.context['tdp_female'], 0)

    def test_the_page_frames_both_programmes(self):
        r = self.c.get('/unifast/reports/?sy=2026-2027')
        body = r.content.decode()
        self.assertIn('/unifast/reports/preview/?sy=2026-2027', body)
        self.assertIn('/unifast/reports/preview/tdp/?sy=2026-2027', body)
        self.assertIn('/unifast/reports/download/tdp/?sy=2026-2027', body)

    # ── The download ────────────────────────────────────────────────────────

    def test_tdp_download_is_tdp_only(self):
        self._scholar('TDP', 'Cruz', 'Female', 'S1')
        self._scholar('TES', 'Reyes', 'Male', 'S2')

        r = self.c.get('/unifast/reports/download/tdp/?sy=2026-2027')
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        self.assertIn('TDP_Scholars_2026_2027.xlsx', r['Content-Disposition'])

        text = sheet_text(r.content, 'TDP Scholars')
        self.assertIn('TULONG DUNONG PROGRAM', text)
        self.assertIn('Cruz', text)
        # The TES grantee belongs to the other report, not this one.
        self.assertNotIn('Reyes', text)

    def test_tdp_download_is_scoped_to_the_school_year(self):
        self._scholar('TDP', 'Cruz', 'Female', 'S1', school_year='2026-2027')
        self._scholar('TDP', 'Reyes', 'Male', 'S2', school_year='2025-2026')

        text = sheet_text(
            self.c.get('/unifast/reports/download/tdp/?sy=2025-2026').content,
            'TDP Scholars')
        self.assertIn('Reyes', text)
        self.assertNotIn('Cruz', text)

    def test_tdp_download_splits_by_gender(self):
        self._scholar('TDP', 'Cruz', 'Female', 'S1')
        self._scholar('TDP', 'Bautista', 'Male', 'S2')
        text = sheet_text(
            self.c.get('/unifast/reports/download/tdp/').content, 'TDP Scholars')
        self.assertIn('FEMALE', text)
        self.assertIn('MALE', text)

    def test_a_year_with_no_tdp_scholars_still_downloads(self):
        r = self.c.get('/unifast/reports/download/tdp/?sy=2024-2025')
        self.assertEqual(r.status_code, 200)
        self.assertIn('No approved scholars for this programme.',
                      sheet_text(r.content, 'TDP Scholars'))

    def test_combined_masterlist_still_carries_both(self):
        self._scholar('TDP', 'Cruz', 'Female', 'S1')
        self._scholar('TES', 'Reyes', 'Male', 'S2')

        text = sheet_text(
            self.c.get('/unifast/reports/download/excel/').content,
            'UniFAST Scholars')
        self.assertIn('Cruz', text)
        self.assertIn('Reyes', text)

    def test_combined_masterlist_takes_the_school_year_too(self):
        self._scholar('TDP', 'Cruz', 'Female', 'S1', school_year='2026-2027')
        self._scholar('TES', 'Reyes', 'Male', 'S2', school_year='2025-2026')

        text = sheet_text(
            self.c.get('/unifast/reports/download/excel/?sy=2026-2027').content,
            'UniFAST Scholars')
        self.assertIn('Cruz', text)
        self.assertNotIn('Reyes', text)

    # ── The preview ─────────────────────────────────────────────────────────

    def test_tdp_frame_serves_the_converted_workbook(self):
        self._scholar('TDP', 'Cruz', 'Female', 'S1')
        with mock.patch('api.doc_convert.available', return_value=True), \
                mock.patch('api.doc_convert.to_pdf',
                           return_value=b'%PDF-1.7 tdp') as convert:
            r = self.c.get('/unifast/reports/preview/tdp/')

        self.assertEqual(r.content, b'%PDF-1.7 tdp')
        source, suffix = convert.call_args[0]
        self.assertEqual(suffix, '.xlsx')
        # What went to the converter is the workbook that downloads.
        self.assertIn('Cruz', sheet_text(source, 'TDP Scholars'))

    def test_tdp_stand_in_is_drawn_when_no_converter_is_installed(self):
        self._scholar('TDP', 'Cruz', 'Female', 'S1')
        with mock.patch('api.doc_convert.available', return_value=False):
            r = self.c.get('/unifast/reports/preview/tdp/')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

        text = pdf_text(r.content)
        self.assertIn('BILIRAN PROVINCE STATE UNIVERSITY', text)
        self.assertIn('TULONG DUNONG PROGRAM', text)
        self.assertIn('Cruz', text)
        self.assertIn('FEMALE', text)

    def test_tdp_preview_renders_with_no_scholars(self):
        with mock.patch('api.doc_convert.available', return_value=False):
            r = self.c.get('/unifast/reports/preview/tdp/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    # ── Who may ask ─────────────────────────────────────────────────────────

    def test_the_tdp_report_is_the_unifast_office_only(self):
        student = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            role='student')
        StudentProfile.objects.create(user=student, student_id='X1')
        c = Client()
        self.assertTrue(c.login(email='s@bipsu.edu.ph', password='pw'))
        for url in ('/unifast/reports/download/tdp/',
                    '/unifast/reports/preview/tdp/'):
            self.assertNotEqual(c.get(url).status_code, 200, url)
