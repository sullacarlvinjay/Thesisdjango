"""Number of scholars per academic year, on the analytics page.

The number this card reports is people, not entries, and that is the whole
difficulty. A scholar enrolled in both semesters of 2025-2026 is on both terms'
lists and is still one scholar, so the year cannot be the sum of its semesters.
Nor can it be the larger of the two: that never double counts, but it drops a
scholar who was on one semester's list and not the other.

So the year's scholars are gathered as a set of people — across its semesters,
across programmes, and across the shapes a scholar's record can take — and
counted once each.
"""
from io import BytesIO

import openpyxl
from django.core.files.base import ContentFile
from django.test import Client, TestCase

from api.models import (
    ImportedScholar, Scholarship, ScholarListImport, SystemSettings, User,
)

# Terms '25-1' and '25-2' are both AY 2025-2026; '26-1' is the year after.
FIRST, SECOND, NEXT_YEAR = '25-1', '25-2', '26-1'
THIS_YEAR, FOLLOWING = '2025-2026', '2026-2027'


class ScholarsPerYearTest(TestCase):

    def setUp(self):
        # An active term of its own, so every term under test is a past one and
        # nothing live is mixed into them.
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '27-1'})
        for stype in ('Academic', 'CHED'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype, category='application',
                description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def listed(self, stype, label, people):
        """`people` as (last, first, student_id) triples on one term's list."""
        ImportedScholar.objects.bulk_create([
            ImportedScholar(scholarship_type=stype, term_label=label,
                            last_name=last, first_name=first, student_id=sid,
                            course='BSCE')
            for last, first, sid in people])

    def years(self, **params):
        r = self.c.get('/vpsea/analytics/', params)
        self.assertEqual(r.status_code, 200)
        return {y['year']: y['scholars'] for y in r.context['year_dist']}

    # ── counting people rather than entries ─────────────────────────────────

    def test_a_scholar_in_both_semesters_is_one_scholar_that_year(self):
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '32-1-00001')])
        self.listed('CHED', SECOND, [('Cruz', 'Ana', '32-1-00001')])
        self.assertEqual(self.years()[THIS_YEAR], 1)

    def test_the_year_is_not_the_larger_semester_either(self):
        """Two terms of two, four people: neither a sum nor a maximum."""
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '32-1-00001'),
                                    ('Lim', 'Ben', '32-1-00002')])
        self.listed('CHED', SECOND, [('Reyes', 'Cara', '32-1-00003'),
                                     ('Tan', 'Dino', '32-1-00004')])
        self.assertEqual(self.years()[THIS_YEAR], 4)

    def test_the_continuing_and_the_new_are_both_counted_once(self):
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '32-1-00001'),
                                    ('Lim', 'Ben', '32-1-00002')])
        self.listed('CHED', SECOND, [('Cruz', 'Ana', '32-1-00001'),
                                     ('Reyes', 'Cara', '32-1-00003')])
        self.assertEqual(self.years()[THIS_YEAR], 3)

    def test_a_scholar_on_two_programmes_is_still_one_scholar(self):
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '32-1-00001')])
        self.listed('Academic', FIRST, [('Cruz', 'Ana', '32-1-00001')])
        self.assertEqual(self.years()[THIS_YEAR], 1)

    def test_each_academic_year_counts_its_own_scholars(self):
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '32-1-00001')])
        self.listed('CHED', NEXT_YEAR, [('Cruz', 'Ana', '32-1-00001')])
        counted = self.years()
        self.assertEqual(counted[THIS_YEAR], 1)
        self.assertEqual(counted[FOLLOWING], 1)

    # ── matching one person across two records of them ──────────────────────

    def test_the_same_student_number_typed_differently_is_one_person(self):
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '32-1-00001')])
        self.listed('CHED', SECOND, [('Cruz', 'Ana', '3210 0001')])
        self.assertEqual(self.years()[THIS_YEAR], 1)

    def test_a_row_with_no_student_number_is_matched_on_its_name(self):
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '')])
        self.listed('CHED', SECOND, [('CRUZ', 'ana ', '')])
        self.assertEqual(self.years()[THIS_YEAR], 1)

    def test_two_different_people_are_two(self):
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '32-1-00001')])
        self.listed('CHED', SECOND, [('Cruz', 'Ana Marie', '32-1-00009')])
        self.assertEqual(self.years()[THIS_YEAR], 2)

    # ── a term held only as an uploaded sheet ───────────────────────────────

    def test_a_term_with_only_a_sheet_is_counted_from_its_names(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['No.', 'Last Name', 'First Name', 'Student Number', 'Course'])
        ws.append([1, 'Cruz', 'Ana', '32-1-00001', 'BSCE'])
        ws.append([2, 'Lim', 'Ben', '32-1-00002', 'BSIT'])
        buf = BytesIO()
        wb.save(buf)

        record = ScholarListImport.objects.create(
            scholarship_type='CHED', term_label=FIRST, scholar_count=2)
        record.excel_file.save('CHED_25-1.xlsx', ContentFile(buf.getvalue()),
                               save=True)
        # …and one of the two continues into the 2nd semester as an imported row.
        self.listed('CHED', SECOND, [('Cruz', 'Ana', '32-1-00001')])

        self.assertEqual(self.years()[THIS_YEAR], 2)

    # ── the card ────────────────────────────────────────────────────────────

    def test_the_page_shows_the_chart_and_the_exact_numbers(self):
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '32-1-00001')])
        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn('Number of Scholars per Academic Year', html)
        self.assertIn('yearChart', html)
        self.assertIn('year-tally', html, 'the exact counts belong on the page too')

    def test_the_card_says_so_when_there_is_nothing_to_count(self):
        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn('Number of Scholars per Academic Year', html)
        self.assertNotIn('yearChart', html)
        self.assertIn('No scholars on record in any academic year', html)

    def test_filtering_to_one_programme_counts_only_that_one(self):
        self.listed('CHED', FIRST, [('Cruz', 'Ana', '32-1-00001')])
        self.listed('Academic', FIRST, [('Lim', 'Ben', '32-1-00002')])
        self.assertEqual(self.years()[THIS_YEAR], 2)
        self.assertEqual(self.years(stype='CHED')[THIS_YEAR], 1)
