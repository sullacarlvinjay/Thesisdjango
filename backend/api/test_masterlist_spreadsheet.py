"""What the downloaded masterlist spreadsheet actually contains.

The existing coverage asserted the filename and the status code, which would
pass over an empty workbook. ``vpsea_report_download_excel`` was 316 lines and
has been rebuilt around one writer class and a row builder per section, so the
cells themselves are read back here — section order, gender bands, headers and
a scholar's values.
"""

from io import BytesIO

import openpyxl
from django.test import TestCase

from api.test_masterlist_report import MasterlistFixtures


def _sheet(response):
    """The single worksheet out of a downloaded spreadsheet."""
    return openpyxl.load_workbook(BytesIO(response.content)).active


def _column(sheet, index=1):
    """One column as a list of trimmed strings."""
    return [str(cell.value).strip() if cell.value is not None else ''
            for cell in sheet[openpyxl.utils.get_column_letter(index)]]


def _row_starting(sheet, first_cell):
    """The first row whose leading cell matches, as a list of values."""
    for row in sheet.iter_rows(values_only=True):
        if row and str(row[0]) == str(first_cell):
            return list(row)
    return None


class MasterlistSpreadsheetTest(MasterlistFixtures, TestCase):

    def _download(self, **query):
        """Fetch the spreadsheet the reports page offers."""
        response = self.c.get('/vpsea/reports/download/excel/', query)
        self.assertEqual(response.status_code, 200)
        return _sheet(response)

    def test_the_university_heading_opens_the_sheet(self):
        column = _column(self._download())
        self.assertEqual(column[0], 'Republic of the Philippines')
        self.assertIn('BILIRAN PROVINCE STATE UNIVERSITY', column[1])
        self.assertIn('LIST OF SCHOLARS FOR 1st Semester SY: 2026-2027', column[2])

    def test_every_programme_gets_a_section_in_the_order_the_office_reads(self):
        headings = [text for text in _column(self._download())
                    if 'SCHOLARSHIP GRANT' in text]
        openers = [text.split(' SCHOLARSHIP GRANT')[0] for text in headings]
        self.assertEqual(openers, [
            'ACADEMIC (@)',
            'BiPSU STAFF (@)',
            'AFFIRMATIVE ACTION (*)',
            'FULL MERIT/ FULL SCHOLAR (*)',
            'HALF MERIT/ PARTIAL SCHOLAR (*)',
            'DOST (*)',
            'GSIS (*)',
            'TERTIARY EDUCATION SUBSIDY -TES (*)',
        ])

    def test_each_section_heading_names_the_term_being_reported_on(self):
        headings = [text for text in _column(self._download())
                    if 'SCHOLARSHIP GRANT' in text]
        for heading in headings:
            with self.subTest(heading=heading):
                self.assertTrue(heading.endswith('1st Semester SY: 2026-2027'))

    def test_a_scholar_lands_in_the_band_their_gender_says(self):
        self._scholar('Academic', 'Cruz', 'Ana', 'F', '2024-0001')
        self._scholar('Academic', 'Bautista', 'Ben', 'M', '2024-0002')

        column = _column(self._download())
        female = column.index('FEMALE')
        male = column.index('MALE')
        rows = [str(cell.value) for cell in
                self._download()['B'][female:male]]
        self.assertIn('Cruz', rows)
        self.assertNotIn('Bautista', rows)

    def test_a_scholar_with_no_recorded_gender_is_still_listed(self):
        self._scholar('Academic', 'Reyes', 'Rio', '', '2024-0007')
        values = [str(cell.value) for row in self._download().iter_rows()
                  for cell in row if cell.value]
        self.assertIn('Reyes', values,
                      'a blank gender dropped the scholar out of both bands')

    def test_an_academic_row_carries_the_cells_the_office_signs_off(self):
        self._scholar('Academic', 'Cruz', 'Ana', 'F', '2024-0001', gwa=1.20)
        row = _row_starting(self._download(), 1)
        self.assertEqual(row[1], 'Cruz')
        self.assertEqual(row[2], 'Ana')
        self.assertEqual(row[4], 'F')
        self.assertEqual(row[5], 'Poblacion')
        self.assertEqual(row[6], 'Naval')
        self.assertEqual(row[7], 'Biliran')
        self.assertEqual(row[8], 'BSCS')
        self.assertEqual(row[10], 1.20)
        self.assertEqual(row[11], 'University Scholar')
        self.assertEqual(row[12], 'ACADEMIC')

    def test_the_academic_standing_column_follows_the_gwa(self):
        self._scholar('Academic', 'Alpha', 'Uni', 'F', '2024-0011', gwa=1.20)
        self._scholar('Academic', 'Bravo', 'Col', 'F', '2024-0012', gwa=1.45)
        self._scholar('Academic', 'Charlie', 'Non', 'F', '2024-0013', gwa=1.90)

        standings = {}
        for row in self._download().iter_rows(values_only=True):
            if row and row[1] in ('Alpha', 'Bravo', 'Charlie'):
                standings[row[1]] = row[11] or ''
        self.assertEqual(standings, {'Alpha': 'University Scholar',
                                     'Bravo': 'College Scholars',
                                     'Charlie': ''})

    def test_an_award_row_carries_the_award_number_and_district(self):
        self._scholar('CHED', 'Lim', 'Lena', 'F', '2024-0003')
        row = _row_starting(self._download(), 1)
        self.assertEqual(row[1], 'AW-2024-0003')
        self.assertEqual(row[2], 'Lim')
        self.assertEqual(row[9], 'Lone District')

    def test_a_staff_row_carries_the_full_rate_for_an_employee(self):
        self._staff('Ernesto Bagayas Dela Pena', gender='M', sid='EMP-07')
        row = None
        for line in self._download().iter_rows(values_only=True):
            if line and line[1] == 'Pena':
                row = list(line)
        self.assertIsNotNone(row, 'the staff scholar never reached the sheet')
        self.assertEqual(row[2], 'Ernesto')
        self.assertEqual(row[3], 'B.')
        self.assertEqual(row[8], '100')
        self.assertEqual(row[9], 'BiPSU STAFF SCHOLARSHIP')

    def test_a_scholar_from_another_term_is_not_in_this_terms_sheet(self):
        award = self._scholar('Academic', 'Reyes', 'Rita', 'F', '2024-0004')
        award.term_label = '25-1'
        award.school_year = '2025-2026'
        award.save()

        values = [str(cell.value) for row in self._download().iter_rows()
                  for cell in row if cell.value]
        self.assertNotIn('Reyes', values,
                         "last term's scholar was listed under this term's heading")

    def test_the_signature_block_is_in_the_page_footer(self):
        sheet = self._download()
        self.assertIn('MARICEL S. SAULAN', sheet.oddFooter.center.text)
        self.assertIn('University President', sheet.oddFooter.center.text)
        self.assertEqual(sheet.oddFooter.center.text, sheet.evenFooter.center.text)

    def test_an_empty_term_still_produces_every_heading(self):
        headings = [text for text in _column(self._download(sy='25-1'))
                    if 'SCHOLARSHIP GRANT' in text]
        self.assertEqual(len(headings), 8,
                         'a term with no scholars lost its section headings')

    def test_columns_are_widened_to_fit_rather_than_left_at_the_default(self):
        self._scholar('Academic', 'Cruz', 'Ana', 'F', '2024-0001')
        sheet = self._download()
        self.assertGreater(sheet.column_dimensions['B'].width, 0)
        self.assertLessEqual(sheet.column_dimensions['A'].width, 35)
