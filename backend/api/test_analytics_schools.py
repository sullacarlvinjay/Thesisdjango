"""How many scholars each BiPSU school has, on the analytics page.

The count has to reconcile three records that disagree about what they know. An
award and a staff application record a school outright. An imported row — which
for every programme without a portal is most of the list — carries a course and
nothing else, and so does the spreadsheet a past semester is read back from.

So the school is read where it is recorded and worked out from the course where
it is not, and a scholar whose course matches none of BiPSU's is reported as
unrecorded rather than filed under a school nobody chose.
"""
from django.test import Client, TestCase

from api.models import (
    AffirmativeStaffApplication, Application, ImportedScholar, Scholarship,
    StudentProfile, SystemSettings, User,
)
from api.student_views import UNRECORDED_SCHOOL

ENGINEERING = 'School of Engineering'
TECH = 'School of Technologies and Computer Studies'


class SchoolTallyTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        self.term = '26-1'
        for stype in ('Academic', 'CHED', 'Staff'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype, category='application',
                description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    # ── fixtures ────────────────────────────────────────────────────────────

    def award(self, n, school, course, stype='Academic'):
        user = User.objects.create_user(
            username=f's{n}@bipsu.edu.ph', email=f's{n}@bipsu.edu.ph',
            password='pw', first_name=f'S{n}', last_name=f'Lim{n}', role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id=f'2022-{n:05d}', school=school, course=course,
            year_level=2)
        return Application.objects.create(
            student=profile, scholarship=Scholarship.objects.get(type=stype),
            status='Approved')

    def imported(self, course, stype='CHED', last='Cruz'):
        return ImportedScholar.objects.create(
            scholarship_type=stype, term_label=self.term, last_name=last,
            first_name='Juan', course=course, year_level=2)

    def tally(self, **params):
        r = self.c.get('/vpsea/analytics/', params)
        self.assertEqual(r.status_code, 200)
        return {row['school']: row['scholars'] for row in r.context['school_dist']}

    # ── the count ───────────────────────────────────────────────────────────

    def test_an_award_is_counted_under_the_school_on_its_record(self):
        self.award(1, ENGINEERING, 'BSCE')
        self.award(2, ENGINEERING, 'BSEE')
        self.assertEqual(self.tally()[ENGINEERING], 2)

    def test_a_blank_school_is_worked_out_from_the_course(self):
        """Students typed their course free-hand for years, so many have no school."""
        self.award(1, '', 'BSCS')
        self.assertEqual(self.tally()[TECH], 1)

    def test_a_course_that_matches_nothing_is_reported_rather_than_guessed(self):
        self.award(1, '', 'Batchelor of Science in Computer Science ')
        self.assertEqual(self.tally()[UNRECORDED_SCHOOL], 1)

    def test_an_imported_row_is_counted_from_its_course(self):
        """Imported rows have no school column at all, and for most programmes
        they are the whole list."""
        self.imported('BSCS')
        self.assertEqual(self.tally()[TECH], 1)

    def test_a_staff_application_is_counted_under_its_own_school(self):
        AffirmativeStaffApplication.objects.create(
            full_name='Rosa Mendoza', contact_number='0918',
            date_of_birth='1990-01-01', course='BSED', year_level=1,
            status='Approved', qualified_for='Staff', school=ENGINEERING)
        self.assertEqual(self.tally()[ENGINEERING], 1)

    def test_the_three_record_shapes_add_up_into_one_tally(self):
        self.award(1, ENGINEERING, 'BSCE')
        self.award(2, '', 'BSCS')
        self.award(3, '', 'nothing on the list')
        self.imported('BSIS')
        AffirmativeStaffApplication.objects.create(
            full_name='Rosa Mendoza', contact_number='0918',
            date_of_birth='1990-01-01', course='BSED', year_level=1,
            status='Approved', qualified_for='Staff', school=ENGINEERING)
        self.assertEqual(self.tally(), {
            TECH: 2,                 # one award by course, one imported row
            ENGINEERING: 2,          # one award, one staff application
            UNRECORDED_SCHOOL: 1,
        })

    def test_the_biggest_school_is_listed_first(self):
        self.award(1, ENGINEERING, 'BSCE')
        self.award(2, TECH, 'BSCS')
        self.award(3, TECH, 'BSIS')
        r = self.c.get('/vpsea/analytics/')
        self.assertEqual([row['school'] for row in r.context['school_dist']][0], TECH)

    def test_only_approved_scholars_are_counted(self):
        award = self.award(1, ENGINEERING, 'BSCE')
        award.status = 'Pending Validation'
        award.save(update_fields=['status'])
        self.assertNotIn(ENGINEERING, self.tally())

    def test_filtering_to_one_programme_counts_only_that_one(self):
        self.award(1, ENGINEERING, 'BSCE')          # Academic
        self.imported('BSCS', stype='CHED')
        self.assertEqual(self.tally(stype='CHED'), {TECH: 1})
        self.assertEqual(self.tally(stype='Academic'), {ENGINEERING: 1})

    # ── the page ────────────────────────────────────────────────────────────

    def test_the_page_shows_the_chart_and_the_exact_numbers(self):
        self.award(1, ENGINEERING, 'BSCE')
        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn('Scholars by School', html)
        self.assertIn('schoolChart', html)
        self.assertIn('school-tally', html, 'the exact counts belong on the page too')
        self.assertIn(ENGINEERING, html)

    def test_the_card_says_so_when_there_is_nothing_to_count(self):
        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn('Scholars by School', html)
        self.assertNotIn('schoolChart', html)

    def test_the_unifast_portal_reads_the_same_tally(self):
        """Both portals share one context builder, so neither can drift."""
        Scholarship.objects.create(name='TES', type='TES', category='application',
                                   description='x', eligibility='x', requirements=[])
        self.imported('BSCS', stype='TES', last='Uy')
        User.objects.create_user(
            username='u@bipsu.edu.ph', email='u@bipsu.edu.ph', password='pw',
            first_name='U', last_name='Officer', role='unifast')
        office = Client()
        self.assertTrue(office.login(email='u@bipsu.edu.ph', password='pw'))
        r = office.get('/unifast/analytics/')
        self.assertEqual(r.status_code, 200)
        tally = {row['school']: row['scholars'] for row in r.context['school_dist']}
        self.assertEqual(tally.get(TECH), 1)
