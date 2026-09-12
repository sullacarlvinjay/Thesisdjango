"""A column the office added is filled from the uploaded sheet, not retyped.

Custom columns could only ever be typed — one scholar at a time, on the archive
page. For the programmes that have a portal that is merely tedious. For the ones
that do not — DOST, CHED, GSIS, CoScho, TDP, most of the catalogue — it was
worse than that: those arrive *entirely* as the agency's spreadsheet, so a
column the funder's own file already carried had to be retyped row by row, and
the next import replaced the term's rows and lost every cell of it again.

The sheet fills it now. Matched on the heading, because position is the one
thing the office's table and a funder's file do not share.

What is deliberately not done is guessing. A heading that does not name an added
column is ignored, a cell holding the wrong kind of thing is refused rather than
stored, and the office is told how many were refused — a half-filled column that
nobody mentioned is the failure this whole feature could most easily become.
"""
import datetime
from io import BytesIO

from openpyxl import Workbook

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import ImportedScholar, Scholarship, SystemSettings, User

# The DOST contract, from COLUMN_HINTS. Anything after it is the funder's own.
CONTRACT = ['No.', 'Award Number', 'Last Name', 'First Name', 'Middle Name',
            'Sex', 'Brgy./St.', 'Municipality', 'Province', 'Congress District',
            'Course', 'Yr.', 'Scholarship Program']


def sheet(extra_headings=(), extra_values=()):
    """One upload: a single scholar, plus whatever columns the funder added."""
    wb = Workbook()
    ws = wb.active
    ws.append(CONTRACT + list(extra_headings))
    ws.append([1, 'AW-1', 'Santos', 'Maria', 'R', 'F', 'Poblacion', 'Naval',
               'Biliran', '1st', 'BSCS', '2', 'DOST']
              + list(extra_values))
    buf = BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(
        'dost.xlsx', buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


class ImportFillsTheColumnsTheOfficeAddedTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-1',
                            'active_semester': '1st Semester'})
        self.programme = Scholarship.objects.create(
            name='DOST Scholarship', type='DOST', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def add_columns(self, *columns):
        self.programme.extra_columns = list(columns)
        self.programme.save(update_fields=['extra_columns'])

    def upload(self, headings=(), values=()):
        return self.c.post('/vpsea/archives/import/', {
            'type': 'DOST', 'rollover_label': '26-1',
            'file': sheet(headings, values)})

    def scholar(self):
        return ImportedScholar.objects.get(last_name='Santos')

    # ── the point of the whole thing ────────────────────────────────────────

    def test_a_heading_that_names_an_added_column_fills_it(self):
        self.add_columns({'key': 'extra_batch', 'label': 'Batch', 'type': 'text'})
        self.upload(['Batch'], ['2026-A'])
        self.assertEqual(self.scholar().extra_data, {'extra_batch': '2026-A'})

    def test_the_match_ignores_case_and_surrounding_space(self):
        """The office names the column; the funder types the heading. Neither
        should have to match the other keystroke for keystroke."""
        self.add_columns({'key': 'extra_batch', 'label': 'Batch', 'type': 'text'})
        self.upload(['  BATCH  '], ['2026-A'])
        self.assertEqual(self.scholar().extra_data, {'extra_batch': '2026-A'})

    def test_two_added_columns_both_fill(self):
        self.add_columns({'key': 'extra_batch', 'label': 'Batch', 'type': 'text'},
                         {'key': 'extra_adviser', 'label': 'Adviser', 'type': 'text'})
        self.upload(['Batch', 'Adviser'], ['2026-A', 'Dr Cruz'])
        self.assertEqual(self.scholar().extra_data,
                         {'extra_batch': '2026-A', 'extra_adviser': 'Dr Cruz'})

    def test_the_order_in_the_file_need_not_match_the_order_on_the_table(self):
        """Matched on the heading, so a funder's file lays out as it likes."""
        self.add_columns({'key': 'extra_batch', 'label': 'Batch', 'type': 'text'},
                         {'key': 'extra_adviser', 'label': 'Adviser', 'type': 'text'})
        self.upload(['Adviser', 'Batch'], ['Dr Cruz', '2026-A'])
        self.assertEqual(self.scholar().extra_data,
                         {'extra_batch': '2026-A', 'extra_adviser': 'Dr Cruz'})

    # ── what it refuses to guess ────────────────────────────────────────────

    def test_a_heading_naming_no_added_column_is_ignored(self):
        self.add_columns({'key': 'extra_batch', 'label': 'Batch', 'type': 'text'})
        self.upload(['Batch', 'Something Else'], ['2026-A', 'ignored'])
        self.assertEqual(self.scholar().extra_data, {'extra_batch': '2026-A'})

    def test_a_near_miss_is_not_treated_as_a_match(self):
        """'Batch No.' is a different column from 'Batch'. Filling one from the
        other would be the import inventing a mapping nobody asked for."""
        self.add_columns({'key': 'extra_batch', 'label': 'Batch', 'type': 'text'})
        self.upload(['Batch No.'], ['2026-A'])
        self.assertEqual(self.scholar().extra_data, {})

    def test_a_programme_with_no_added_columns_is_untouched(self):
        self.upload(['Batch'], ['2026-A'])
        self.assertEqual(self.scholar().extra_data, {})

    def test_a_contract_column_is_never_read_twice(self):
        """A heading matching an added column, sitting where the import contract
        already reads something else, must not have its value taken for both."""
        self.add_columns({'key': 'extra_sex', 'label': 'Sex', 'type': 'text'})
        self.upload()
        scholar = self.scholar()
        self.assertEqual(scholar.gender, 'F')
        self.assertEqual(scholar.extra_data, {})

    # ── the declared kind still holds ───────────────────────────────────────

    def test_a_number_column_takes_a_number(self):
        self.add_columns({'key': 'extra_stipend', 'label': 'Stipend',
                          'type': 'number'})
        self.upload(['Stipend'], [7500])
        self.assertEqual(self.scholar().extra_data, {'extra_stipend': '7500'})

    def test_a_number_column_refuses_a_word_and_says_how_many(self):
        self.add_columns({'key': 'extra_stipend', 'label': 'Stipend',
                          'type': 'number'})
        response = self.upload(['Stipend'], ['not a number'])
        self.assertEqual(self.scholar().extra_data, {})
        self.assertIn('columns_bad=1', response['Location'])

    def test_a_date_column_takes_a_real_excel_date(self):
        """Excel stores a date as a datetime, not as text. Left untranslated,
        clean_value refuses it — so a Date column would have rejected every
        properly formatted date in the file and kept only the typed ones."""
        self.add_columns({'key': 'extra_awarded', 'label': 'Awarded',
                          'type': 'date'})
        self.upload(['Awarded'], [datetime.datetime(2026, 6, 7)])
        self.assertEqual(self.scholar().extra_data, {'extra_awarded': '2026-06-07'})

    def test_a_choice_column_takes_only_its_own_options(self):
        self.add_columns({'key': 'extra_track', 'label': 'Track', 'type': 'choice',
                          'options': ['RA 7687', 'Merit']})
        self.upload(['Track'], ['Merit'])
        self.assertEqual(self.scholar().extra_data, {'extra_track': 'Merit'})

    def test_a_choice_column_refuses_an_answer_not_on_its_list(self):
        self.add_columns({'key': 'extra_track', 'label': 'Track', 'type': 'choice',
                          'options': ['RA 7687', 'Merit']})
        response = self.upload(['Track'], ['Platinum'])
        self.assertEqual(self.scholar().extra_data, {})
        self.assertIn('columns_bad=1', response['Location'])

    def test_a_blank_cell_is_left_blank_rather_than_refused(self):
        """A column the office added is not one every scholar has an answer for,
        so an empty cell is an answer and not a fault to report."""
        self.add_columns({'key': 'extra_batch', 'label': 'Batch', 'type': 'text'})
        response = self.upload(['Batch'], [None])
        self.assertEqual(self.scholar().extra_data, {})
        self.assertNotIn('columns_bad', response['Location'])

    # ── it reaches the screen ───────────────────────────────────────────────

    def test_the_value_shows_on_the_archive_table(self):
        """Imported and then read back through the page, so the round trip is
        the one the office actually sees rather than a row in the database."""
        self.add_columns({'key': 'extra_batch', 'label': 'Batch', 'type': 'text'})
        self.upload(['Batch'], ['2026-A'])
        self.programme.table_columns = ['last_name']
        self.programme.save(update_fields=['table_columns'])

        html = self.c.get('/vpsea/archives/',
                          {'type': 'DOST'}).content.decode()
        self.assertIn('Batch', html)
        self.assertIn('2026-A', html)

    def test_a_clean_import_says_nothing_about_refused_cells(self):
        self.add_columns({'key': 'extra_batch', 'label': 'Batch', 'type': 'text'})
        response = self.upload(['Batch'], ['2026-A'])
        self.assertIn('import_ok=1', response['Location'])
        self.assertNotIn('columns_bad', response['Location'])
