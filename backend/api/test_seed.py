from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Count
from django.test import TestCase

from .models import (
    ApplicantRecord, Application, Announcement, Scholarship, StudentProfile,
    SystemSettings,
)

User = get_user_model()

DEMO = 'juan.delacruz@bipsu.edu.ph'


def run():
    out = StringIO()
    call_command('seed', stdout=out)
    return out.getvalue()


class SeedTest(TestCase):

    def test_it_gets_all_the_way_through_a_clean_database(self):
        output = run()

        self.assertIn('seeded successfully', output)
        self.assertTrue(SystemSettings.objects.filter(pk=1).exists())
        self.assertTrue(Scholarship.objects.exists())
        self.assertTrue(Announcement.objects.exists())

    def test_it_creates_the_three_advertised_accounts(self):
        run()
        for email, password in (
            ('it@bipsu.edu.ph', 'admin1234'),
            ('vpsea@bipsu.edu.ph', 'vpsea1234'),
            (DEMO, 'demo1234'),
        ):
            self.assertTrue(
                User.objects.get(email=email).check_password(password),
                f'{email} cannot sign in with the password seed prints')

    def test_the_demo_students_history_spans_two_school_years(self):
        run()
        profile = StudentProfile.objects.get(user__email=DEMO)
        years = set(Application.objects.filter(student=profile)
                    .values_list('school_year', flat=True))

        self.assertEqual(len(years), 2, f'history sits in one term: {years}')

    def test_the_demo_student_keeps_every_row_of_that_history(self):
        run()
        profile = StudentProfile.objects.get(user__email=DEMO)
        self.assertEqual(Application.objects.filter(student=profile).count(), 4)

    def test_no_student_holds_one_programme_twice_in_a_term(self):
        run()
        clashes = (Application.objects
                   .values('student', 'scholarship', 'school_year', 'semester')
                   .annotate(seen=Count('pk')).filter(seen__gt=1))

        self.assertFalse(list(clashes))

    def test_every_archive_scholar_gets_an_approved_award(self):
        run()
        for kind in ('Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'GSIS'):
            self.assertTrue(
                Application.objects.filter(scholarship__type=kind,
                                           status='Approved').exists(),
                f'the archives have no approved {kind} scholar to show')

    def test_running_it_twice_creates_nothing_the_second_time(self):
        run()
        before = (User.objects.count(), Application.objects.count(),
                  StudentProfile.objects.count(), ApplicantRecord.objects.count(),
                  Announcement.objects.count())

        run()

        self.assertEqual(
            (User.objects.count(), Application.objects.count(),
             StudentProfile.objects.count(), ApplicantRecord.objects.count(),
             Announcement.objects.count()),
            before)
