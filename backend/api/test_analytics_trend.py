"""Scholars Over Time plots one line per programme, not one blended total.

The total is what the summary tiles already say. What the chart is for is the
comparison between programmes — which are growing, which are shrinking — and
that needs a series each. Filtering the page to one programme draws that one
alone.
"""
from django.test import Client, TestCase

from api.models import (
    Application, ImportedScholar, Scholarship, ScholarListImport,
    StudentProfile, SystemSettings, User,
)

ALL_TYPES = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports',
             'Affirmative', 'Staff', 'GSIS', 'TES']


class ScholarsOverTimeTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        for stype in ALL_TYPES:
            Scholarship.objects.create(
                name=stype, type=stype, category='application',
                description='x', eligibility='x', requirements=[],
            )
        User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw', role='vpsea',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='vpsea@bipsu.edu.ph', password='pw'))

    def _past(self, stype, label, count):
        """Scholars in a semester that has already been rolled over."""
        ScholarListImport.objects.create(
            scholarship_type=stype, school_year='2025-2026', semester='2nd Semester',
            term_label=label, scholar_count=count)
        for i in range(count):
            ImportedScholar.objects.create(
                scholarship_type=stype, term_label=label,
                last_name=f'{stype}{i}', first_name='Test')

    def _current(self, stype, sid):
        """An approved award in the active term."""
        u = User.objects.create_user(
            username=f'{sid}@bipsu.edu.ph', email=f'{sid}@bipsu.edu.ph', password='pw',
            first_name='Test', last_name=sid, role='student',
        )
        p = StudentProfile.objects.create(user=u, student_id=sid, course='BSCS', year_level=2)
        return Application.objects.create(
            student=p, scholarship=Scholarship.objects.get(type=stype),
            status='Approved', term_label='26-1')

    def _series(self, stype=None):
        url = '/vpsea/analytics/' + (f'?stype={stype}' if stype else '')
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200)
        return r, {s['type']: s['counts'] for s in r.context['trend_series']}

    # ── one line per programme ──────────────────────────────────────────────

    def test_each_programme_with_scholars_gets_its_own_series(self):
        self._past('Academic', '25-2', 3)
        self._past('TDP', '25-2', 2)
        self._current('Academic', '2024-0001')

        _, series = self._series()
        self.assertEqual(series['Academic'], [3, 1])
        self.assertEqual(series['TDP'], [2, 0])

    def test_a_programme_with_no_scholars_anywhere_is_left_out(self):
        self._past('Academic', '25-2', 3)
        _, series = self._series()
        self.assertIn('Academic', series)
        for empty in ('DOST', 'CHED', 'CoScho', 'Sports', 'GSIS'):
            self.assertNotIn(empty, series)

    def test_a_gap_is_a_zero_not_a_missing_point(self):
        """Every series must be the same length or the lines stop lining up."""
        self._past('TDP', '25-2', 5)
        self._current('Academic', '2024-0002')

        r, series = self._series()
        span = len(r.context['trend_data'])
        self.assertEqual(series['TDP'], [5, 0])
        self.assertEqual(series['Academic'], [0, 1])
        for counts in series.values():
            self.assertEqual(len(counts), span)

    def test_the_totals_still_add_up(self):
        self._past('Academic', '25-2', 3)
        self._past('TDP', '25-2', 2)

        r, series = self._series()
        first_semester_total = r.context['trend_data'][0]['total']
        self.assertEqual(first_semester_total, 5)
        self.assertEqual(sum(c[0] for c in series.values()), first_semester_total)

    # ── filtered to one programme ───────────────────────────────────────────

    def test_selecting_a_programme_draws_that_one_alone(self):
        self._past('Academic', '25-2', 3)
        self._past('TDP', '25-2', 2)

        _, series = self._series('Academic')
        self.assertEqual(list(series), ['Academic'])
        self.assertEqual(series['Academic'], [3, 0])

    def test_selecting_a_programme_with_no_scholars_still_draws_its_line(self):
        """An empty line is an answer — it says the programme has nobody."""
        self._past('Academic', '25-2', 3)
        _, series = self._series('DOST')
        self.assertEqual(list(series), ['DOST'])
        self.assertEqual(set(series['DOST']), {0})

    # ── the other office sees only its own programmes ───────────────────────

    def test_unifast_sees_only_its_own_programmes(self):
        self._past('Academic', '25-2', 3)
        self._past('TDP', '25-2', 2)
        self._past('TES', '25-2', 1)

        User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
            password='pw', role='unifast',
        )
        office = Client()
        self.assertTrue(office.login(email='unifast@bipsu.edu.ph', password='pw'))
        r = office.get('/unifast/analytics/')
        series = {s['type'] for s in r.context['trend_series']}
        self.assertEqual(series, {'TDP', 'TES'})
        self.assertNotIn('Academic', series)
