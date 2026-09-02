"""The CHED Annex 1 report — the list of TES applicants — and the year picker.

Two things are being guarded here. The workbook: that it is the office's own
template with the applicant rows written into it, macros and dropdowns intact,
rather than a sheet recreated in code. And the school year: that picking one
scopes the applicants page, the Annex 1 download and the Annex 2 report alike,
so what an officer looks at is what they generate.
"""
import openpyxl
from datetime import date
from io import BytesIO

from django.test import TestCase, Client

from api import annex1_report, tes_report
from api.models import (
    User, StudentProfile, Scholarship, TESApplication, SystemSettings,
)


class Annex1ReportTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        Scholarship.objects.create(
            name='TES', type='TES', category='application',
            description='x', eligibility='x', requirements=[],
        )
        self.unifast = User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
            password='pw', role='unifast',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='unifast@bipsu.edu.ph', password='pw'))

    def _applicant(self, last, sid, school_year='2026-2027', **kwargs):
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph',
            password='pw', first_name='Juan', last_name=last, role='student',
        )
        p = StudentProfile.objects.create(
            user=u, student_id=sid, course='BSCS', year_level=2,
            gender='Female', middle_name='Santos', suffix='Jr.',
            contact_number='09171234567',
        )
        p.father_last_name = last
        p.father_first_name = 'Pedro'
        p.mother_last_name = 'Reyes'
        p.mother_first_name = 'Maria'
        p.save()
        fields = {
            'lrn': '123456789012',
            'birthdate': date(2005, 3, 14),
            'complete_program': 'BACHELOR OF SCIENCE IN COMPUTER SCIENCE',
            'street_barangay': 'Purok 1, Poblacion',
            'city_municipality': 'Naval',
            'province': 'Biliran',
            'region': 'Region VIII',
            'zip_code': '6560',
            'contact_number': '09171234567',
            'email_address': f'{sid}@bipsu.edu.ph',
        }
        fields.update(kwargs)
        return TESApplication.objects.create(
            student=p, school_year=school_year, semester='1st Semester', **fields)

    # ── The rows ────────────────────────────────────────────────────────────

    def test_every_applicant_is_listed_whatever_the_decision(self):
        """Annex 1 is the applicant list, not the grantee list."""
        self._applicant('Cruz', 'S1', status='Pending')
        self._applicant('Bautista', 'S2', status='Approved')
        self._applicant('Aquino', 'S3', status='Rejected')

        rows = annex1_report.applicant_rows(school_year='2026-2027')

        self.assertEqual([r['last_name'] for r in rows],
                         ['Aquino', 'Bautista', 'Cruz'])
        self.assertEqual([r['seq'] for r in rows], [1, 2, 3])

    def test_rows_are_scoped_to_the_school_year(self):
        self._applicant('Cruz', 'S1', school_year='2026-2027')
        self._applicant('Reyes', 'S2', school_year='2025-2026')

        self.assertEqual(
            [r['last_name'] for r in annex1_report.applicant_rows(school_year='2026-2027')],
            ['Cruz'])
        self.assertEqual(
            [r['last_name'] for r in annex1_report.applicant_rows(school_year='2025-2026')],
            ['Reyes'])
        # No year means every year, which is how the review queue reads.
        self.assertEqual(len(annex1_report.applicant_rows()), 2)

    def test_sex_is_the_code_the_form_validates_against(self):
        """0 = Male, 1 = Female — the Sex_Code sheet, not the word."""
        self._applicant('Cruz', 'S1')
        male = self._applicant('Reyes', 'S2')
        male.student.gender = 'Male'
        male.student.save()

        rows = {r['last_name']: r['sex'] for r in annex1_report.applicant_rows()}
        self.assertEqual(rows['Cruz'], 1)
        self.assertEqual(rows['Reyes'], 0)

    def test_mobile_number_loses_its_leading_zero(self):
        """CHED asks for 10 digits starting with 9; the profile holds 11 with a 0."""
        self._applicant('Cruz', 'S1', contact_number='0917 123 4567')
        self.assertEqual(annex1_report.applicant_rows()[0]['contact'], '9171234567')

    def test_a_landline_is_passed_through_unchanged(self):
        self._applicant('Cruz', 'S1', contact_number='53500123')
        self.assertEqual(annex1_report.applicant_rows()[0]['contact'], '53500123')

    def test_blank_disability_and_ip_group_export_as_no(self):
        """Both columns spell 'not applicable' as NO on this form."""
        self._applicant('Cruz', 'S1', disability_type='', indigenous_people_group='')
        row = annex1_report.applicant_rows()[0]
        self.assertEqual(row['disability'], 'NO')
        self.assertEqual(row['ip_group'], 'NO')

    def test_a_real_disability_is_kept(self):
        self._applicant('Cruz', 'S1', disability_type='Visual Disability')
        self.assertEqual(annex1_report.applicant_rows()[0]['disability'],
                         'Visual Disability')

    def test_priority_flags_export_as_one_and_zero(self):
        self._applicant('Cruz', 'S1', is_solo_parent_dependent=True,
                        is_first_gen_college=False)
        row = annex1_report.applicant_rows()[0]
        self.assertEqual(row['solo_parent'], 1)
        self.assertEqual(row['first_gen'], 0)

    def test_uncollected_id_numbers_export_blank(self):
        """PhilSys and 4Ps IDs are optional and this system never asks for them."""
        self._applicant('Cruz', 'S1')
        row = annex1_report.applicant_rows()[0]
        self.assertEqual(row['philsys_id'], '')
        self.assertEqual(row['four_ps_id'], '')

    def test_row_values_match_the_header_count(self):
        self._applicant('Cruz', 'S1')
        values = annex1_report.row_values(annex1_report.applicant_rows()[0])
        self.assertEqual(len(values), len(annex1_report.ANNEX1_HEADERS))

    # ── The workbook ────────────────────────────────────────────────────────

    def test_workbook_is_the_office_template_with_rows_written_in(self):
        self._applicant('Cruz', 'S1')
        buf, written, overflow = annex1_report.build_workbook('2026-2027')
        self.assertEqual((written, overflow), (1, 0))

        wb = openpyxl.load_workbook(BytesIO(buf.getvalue()))
        # The template's own sheets, not a workbook built here.
        self.assertIn('Annex 1', wb.sheetnames)
        self.assertIn('General Instructions', wb.sheetnames)
        self.assertIn('Registry_Courses', wb.sheetnames)

        ws = wb['Annex 1']
        self.assertEqual(ws['A1'].value, 'Academic Year 2026-2027')
        self.assertEqual(ws['A3'].value, 'LIST OF TES APPLICANTS')

        first = annex1_report.FIRST_ROW
        self.assertEqual(ws.cell(row=first, column=1).value, 1)      # SEQ
        self.assertEqual(ws.cell(row=first, column=2).value, 'S1')   # STUDENT ID
        self.assertEqual(ws.cell(row=first, column=6).value, 'Cruz')  # LAST NAME
        self.assertEqual(ws.cell(row=first, column=10).value, 1)     # SEX
        self.assertEqual(ws.cell(row=first, column=25).value, '9171234567')

    def test_workbook_keeps_its_dropdowns(self):
        """The Sex, Program and Disability validations must survive the fill."""
        self._applicant('Cruz', 'S1')
        buf, _written, _overflow = annex1_report.build_workbook('2026-2027')
        ws = openpyxl.load_workbook(BytesIO(buf.getvalue()))['Annex 1']
        sources = {dv.formula1 for dv in ws.data_validations.dataValidation}
        self.assertIn('Sex_Code!$A$2:$A$3', sources)
        self.assertIn('Registry_Courses!$A$2:$A$41', sources)
        self.assertIn('Disability_List!$A$2:$A$12', sources)

    def test_workbook_keeps_its_macros(self):
        """It ships as .xlsm; a save that dropped the VBA would break the form."""
        self._applicant('Cruz', 'S1')
        buf, _written, _overflow = annex1_report.build_workbook('2026-2027')
        wb = openpyxl.load_workbook(BytesIO(buf.getvalue()), keep_vba=True)
        self.assertIsNotNone(wb.vba_archive)

    def test_workbook_scopes_itself_to_the_year_it_is_titled_with(self):
        self._applicant('Cruz', 'S1', school_year='2026-2027')
        self._applicant('Reyes', 'S2', school_year='2025-2026')

        buf, written, _overflow = annex1_report.build_workbook('2025-2026')
        self.assertEqual(written, 1)
        ws = openpyxl.load_workbook(BytesIO(buf.getvalue()))['Annex 1']
        self.assertEqual(ws['A1'].value, 'Academic Year 2025-2026')
        self.assertEqual(ws.cell(row=annex1_report.FIRST_ROW, column=6).value, 'Reyes')

    def test_a_year_with_no_applicants_builds_an_empty_form(self):
        buf, written, overflow = annex1_report.build_workbook('2024-2025')
        self.assertEqual((written, overflow), (0, 0))
        ws = openpyxl.load_workbook(BytesIO(buf.getvalue()))['Annex 1']
        self.assertIsNone(ws.cell(row=annex1_report.FIRST_ROW, column=2).value)

    # ── The school-year options ─────────────────────────────────────────────

    def test_year_options_cover_the_data_and_the_active_term(self):
        self._applicant('Cruz', 'S1', school_year='2025-2026')
        # 2026-2027 is the active term and has no applications yet; it is still
        # offered, or the office could not report on the year it is working in.
        self.assertEqual(tes_report.school_year_options(),
                         ['2026-2027', '2025-2026'])

    def test_year_options_are_not_repeated(self):
        self._applicant('Cruz', 'S1', school_year='2026-2027')
        self._applicant('Reyes', 'S2', school_year='2026-2027')
        self.assertEqual(tes_report.school_year_options(), ['2026-2027'])

    # ── The pages ───────────────────────────────────────────────────────────

    def test_applications_page_offers_the_years_and_the_generator(self):
        self._applicant('Cruz', 'S1')
        r = self.c.get('/unifast/tes-applications/')
        self.assertContains(r, '/unifast/tes-applications/report/')
        self.assertContains(r, 'All school years')
        self.assertContains(r, '2026-2027')

    def test_the_controls_sit_on_the_applications_card(self):
        """No generator panel of its own — they are on the list they act on."""
        r = self.c.get('/unifast/tes-applications/')
        body = r.content.decode()
        self.assertNotIn('Generate report', body)
        # Head of the TES Applications card, above its own table.
        self.assertIn('report-gen-head', body)
        self.assertIn('data-preview-open="annex1Preview"', body)

    def test_applications_page_narrows_to_the_chosen_year(self):
        self._applicant('Cruz', 'S1', school_year='2026-2027')
        self._applicant('Reyes', 'S2', school_year='2025-2026')

        r = self.c.get('/unifast/tes-applications/?sy=2025-2026')
        self.assertEqual(r.context['total'], 1)
        self.assertEqual([a['last_name'] for a in r.context['annex1_rows']], ['Reyes'])
        self.assertContains(r, 'Reyes')
        self.assertNotContains(r, 'S1')

    def test_download_is_an_xlsm_named_for_the_year(self):
        self._applicant('Cruz', 'S1')
        r = self.c.get('/unifast/tes-applications/report/?sy=2026-2027')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'],
                         'application/vnd.ms-excel.sheet.macroEnabled.12')
        self.assertIn('TES_Annex1_Applicants_2026_2027.xlsm', r['Content-Disposition'])

        ws = openpyxl.load_workbook(BytesIO(r.content))['Annex 1']
        self.assertEqual(ws.cell(row=annex1_report.FIRST_ROW, column=6).value, 'Cruz')

    def test_download_without_a_year_says_so_in_the_filename(self):
        self._applicant('Cruz', 'S1')
        r = self.c.get('/unifast/tes-applications/report/')
        self.assertIn('TES_Annex1_Applicants_all_years.xlsm', r['Content-Disposition'])

    def test_report_is_the_unifast_office_only(self):
        student = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            role='student')
        StudentProfile.objects.create(user=student, student_id='X1')
        c = Client()
        self.assertTrue(c.login(email='s@bipsu.edu.ph', password='pw'))
        r = c.get('/unifast/tes-applications/report/')
        self.assertNotEqual(r.status_code, 200)

    # ── The year picker on the Reports page ─────────────────────────────────

    def test_reports_page_offers_the_year_picker(self):
        r = self.c.get('/unifast/reports/')
        self.assertContains(r, 'All school years')
        self.assertContains(r, 'name="sy"')
        self.assertEqual(r.context['school_years'], ['2026-2027'])

    def test_reports_page_scopes_the_grantee_list_to_the_year(self):
        self._applicant('Cruz', 'S1', school_year='2026-2027', status='Approved')
        self._applicant('Reyes', 'S2', school_year='2025-2026', status='Approved')

        r = self.c.get('/unifast/reports/?sy=2025-2026')
        self.assertEqual(r.context['tes_total'], 1)
        self.assertEqual(r.context['ay'], '2025-2026')
        self.assertEqual([row['last_name'] for row in r.context['rows']], ['Reyes'])

    def test_reports_page_defaults_to_every_year(self):
        """Unchanged behaviour until a year is chosen."""
        self._applicant('Cruz', 'S1', school_year='2026-2027', status='Approved')
        self._applicant('Reyes', 'S2', school_year='2025-2026', status='Approved')

        r = self.c.get('/unifast/reports/')
        self.assertEqual(r.context['tes_total'], 2)

    def test_annex2_download_is_named_and_titled_for_the_chosen_year(self):
        self._applicant('Reyes', 'S2', school_year='2025-2026', status='Approved')
        r = self.c.get('/unifast/reports/download/tes/?sy=2025-2026')
        self.assertEqual(r.status_code, 200)
        self.assertIn('TES_Validation_Billing_2025_2026.xlsx', r['Content-Disposition'])

        ws = openpyxl.load_workbook(BytesIO(r.content))['Official List']
        self.assertIn('AY 2025-2026', ws['A3'].value)
        self.assertEqual(ws.cell(row=tes_report.OFFICIAL_LIST['first_row'],
                                 column=4).value, 'Reyes')

    def test_annex2_grantee_rows_still_default_to_every_year(self):
        self._applicant('Cruz', 'S1', school_year='2026-2027', status='Approved')
        self._applicant('Reyes', 'S2', school_year='2025-2026', status='Approved')
        self.assertEqual(len(tes_report.grantee_rows()), 2)
