from django.test import Client, TestCase

from api import staff_ranking
from api.models import (
    AffirmativeStaffApplication, StaffProfile, SystemSettings, User,
)


def an_application(**overrides):
    data = {
        'full_name': 'Juan Dela Cruz',
        'email': 'juan@bipsu.edu.ph',
        'qualified_for': 'Staff',
        'date_of_birth': '2000-01-01',
    }
    data.update(overrides)
    return AffirmativeStaffApplication.objects.create(**data)


def an_employee(employee_id='32-1-000001', status='Regular', name='Maria Santos'):
    first, last = name.split(' ', 1)
    user = User.objects.create_user(
        username=f'{employee_id}@bipsu.edu.ph', email=f'{employee_id}@bipsu.edu.ph',
        password='pw', first_name=first, last_name=last, role='nsu_staff')
    staff = StaffProfile.objects.create(user=user, employee_id=employee_id)
    staff.employment_status = status
    staff.save()
    return staff


class QualificationATest(TestCase):
    def test_a_regular_employee_qualifies(self):
        e = staff_ranking.evaluate(an_application(is_nsu_staff=True,
                                                  employment_status='Regular'))
        self.assertEqual(e.status, staff_ranking.QUALIFIED)
        self.assertEqual(e.standing, staff_ranking.STAFF)
        self.assertEqual(e.recommendation, 'Recommended')

    def test_the_boards_own_word_for_it_is_accepted_too(self):
        e = staff_ranking.evaluate(an_application(is_nsu_staff=True,
                                                  employment_status='Permanent'))
        self.assertEqual(e.status, staff_ranking.QUALIFIED)

    def test_a_contractual_employee_does_not(self):
        e = staff_ranking.evaluate(an_application(is_nsu_staff=True,
                                                  employment_status='Contractual'))
        self.assertEqual(e.status, staff_ranking.NOT_QUALIFIED)
        self.assertEqual(e.rule('permanent').verdict, staff_ranking.FAIL)

    def test_a_blank_appointment_is_unknown_rather_than_failed(self):
        e = staff_ranking.evaluate(an_application(is_nsu_staff=True,
                                                  employment_status=''))
        self.assertEqual(e.status, staff_ranking.FOR_VERIFICATION)
        self.assertIn('Employment status on the application', e.missing)

    def test_an_employee_is_not_asked_to_prove_a_dependency(self):
        e = staff_ranking.evaluate(an_application(is_nsu_staff=True,
                                                  employment_status='Regular'))
        self.assertTrue(e.rule('dependency').passed)
        self.assertIn('the applicant is the employee', e.rule('dependency').detail)

    def test_an_employee_with_a_degree_already_is_still_qualified(self):
        e = staff_ranking.evaluate(an_application(
            is_nsu_staff=True, employment_status='Regular', has_baccalaureate=True))
        self.assertEqual(e.status, staff_ranking.QUALIFIED)
        self.assertTrue(e.rule('baccalaureate').passed)


class QualificationBTest(TestCase):
    def setUp(self):
        self.employee = an_employee()

    def _dependent(self, **overrides):
        data = {
            'is_nsu_dependent': True,
            'staff_employee_id': self.employee.employee_id,
            'staff_name': 'Maria Santos',
            'relationship_to_staff': 'Daughter',
        }
        data.update(overrides)
        return staff_ranking.evaluate(an_application(**data))

    def test_the_dependent_of_a_regular_employee_qualifies(self):
        e = self._dependent()
        self.assertEqual(e.status, staff_ranking.QUALIFIED)
        self.assertEqual(e.standing, staff_ranking.DEPENDENT)

    def test_the_appointment_checked_is_the_employees_not_the_dependents(self):
        e = self._dependent()
        self.assertIn('Maria Santos', e.rule('permanent').detail)
        self.assertEqual(e.rule('permanent').source, 'StaffProfile.employment_status')

    def test_the_dependent_of_a_contractual_employee_does_not(self):
        self.employee.employment_status = 'Contractual'
        self.employee.save()
        e = self._dependent()
        self.assertEqual(e.status, staff_ranking.NOT_QUALIFIED)

    def test_an_employee_id_matching_nothing_is_unknown_rather_than_failed(self):
        e = self._dependent(staff_employee_id='32-9-999999')
        self.assertEqual(e.status, staff_ranking.FOR_VERIFICATION)
        self.assertIn('A staff record for employee ID 32-9-999999', e.missing)

    def test_and_the_office_is_told_the_id_it_could_not_find(self):
        e = self._dependent(staff_employee_id='32-9-999999')
        self.assertIn('32-9-999999', e.rule('permanent').detail)

    def test_no_employee_id_at_all_is_unknown_too(self):
        e = self._dependent(staff_employee_id='')
        self.assertEqual(e.status, staff_ranking.FOR_VERIFICATION)
        self.assertIn('Employee ID of the faculty or staff member', e.missing)

    def test_a_dependency_nobody_stated_is_not_established(self):
        e = self._dependent(relationship_to_staff='')
        self.assertEqual(e.status, staff_ranking.FOR_VERIFICATION)
        self.assertIn('Relationship to the faculty or staff member', e.missing)


class QualificationCTest(TestCase):
    def setUp(self):
        self.employee = an_employee()

    def _dependent(self, **overrides):
        data = {
            'is_nsu_dependent': True,
            'staff_employee_id': self.employee.employee_id,
            'staff_name': 'Maria Santos',
            'relationship_to_staff': 'Son',
        }
        data.update(overrides)
        return staff_ranking.evaluate(an_application(**data))

    def test_a_graduate_dependent_is_disqualified(self):
        e = self._dependent(has_baccalaureate=True)
        self.assertEqual(e.status, staff_ranking.NOT_QUALIFIED)
        self.assertEqual(e.rule('baccalaureate').verdict, staff_ranking.FAIL)
        self.assertEqual(e.recommendation, 'Not Recommended')

    def test_even_when_every_other_qualification_is_met(self):
        e = self._dependent(has_baccalaureate=True)
        self.assertTrue(e.rule('permanent').passed)
        self.assertTrue(e.rule('dependency').passed)
        self.assertEqual(e.status, staff_ranking.NOT_QUALIFIED)

    def test_a_failure_settles_it_without_chasing_what_is_missing(self):
        e = self._dependent(staff_employee_id='32-9-999999', has_baccalaureate=True)
        self.assertEqual(e.status, staff_ranking.NOT_QUALIFIED)
        self.assertEqual(e.missing, [])


class StandingTest(TestCase):
    def test_neither_is_unknown_rather_than_a_refusal(self):
        e = staff_ranking.evaluate(an_application())
        self.assertEqual(e.standing, staff_ranking.UNSTATED)
        self.assertEqual(e.status, staff_ranking.FOR_VERIFICATION)

    def test_both_at_once_is_unknown_too(self):
        e = staff_ranking.evaluate(an_application(
            is_nsu_staff=True, is_nsu_dependent=True, employment_status='Regular'))
        self.assertEqual(e.status, staff_ranking.FOR_VERIFICATION)


class RankingOrderTest(TestCase):
    def test_settled_answers_sort_above_the_ones_still_being_checked(self):
        an_application(full_name='Zoe Unknown', email='z@bipsu.edu.ph')
        an_application(full_name='Ana Qualified', email='a@bipsu.edu.ph',
                       is_nsu_staff=True, employment_status='Regular')
        an_application(full_name='Ben Refused', email='b@bipsu.edu.ph',
                       is_nsu_staff=True, employment_status='Job Order')
        order = [e.applicant_name for e in
                 staff_ranking.rank(AffirmativeStaffApplication.objects.all())]
        self.assertEqual(order, ['Ana Qualified', 'Zoe Unknown', 'Ben Refused'])

    def test_everyone_appears_including_the_undecidable(self):
        an_application(full_name='Zoe Unknown', email='z@bipsu.edu.ph')
        self.assertEqual(
            len(staff_ranking.rank(AffirmativeStaffApplication.objects.all())), 1)

    def test_nothing_is_written_by_evaluating(self):
        application = an_application(is_nsu_staff=True, employment_status='Regular')
        before = application.updated_at
        staff_ranking.rank(AffirmativeStaffApplication.objects.all())
        application.refresh_from_db()
        self.assertEqual(application.updated_at, before)


class TheTabTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def test_the_ranking_page_offers_it(self):
        self.assertContains(self.c.get('/vpsea/ranking/'),
                            '/vpsea/ranking/?type=Staff')

    def test_the_tab_prints_the_three_qualifications(self):
        html = ' '.join(self.c.get('/vpsea/ranking/?type=Staff')
                        .content.decode().split())
        for qualification in ('permanent appointment',
                              'legitimate dependents',
                              '<strong>already graduated a baccalaureate degree</strong>'):
            with self.subTest(qualification=qualification):
                self.assertIn(qualification, html)

    def test_an_applicant_appears_with_their_verdict(self):
        an_application(full_name='Juan Dela Cruz', is_nsu_staff=True,
                       employment_status='Regular')
        page = self.c.get('/vpsea/ranking/?type=Staff')
        self.assertContains(page, 'Juan Dela Cruz')
        self.assertContains(page, 'Recommended')

    def test_an_undecidable_one_is_held_out_with_what_is_missing(self):
        an_application(full_name='Zoe Unknown')
        page = self.c.get('/vpsea/ranking/?type=Staff')
        self.assertContains(page, 'Applied, but not yet decidable')
        self.assertContains(page, 'Whether the applicant is the employee')

    def test_an_empty_programme_says_so_rather_than_showing_an_empty_table(self):
        self.assertContains(self.c.get('/vpsea/ranking/?type=Staff'),
                            'Nobody has applied')

    def test_affirmative_applications_are_not_screened_here(self):
        an_application(full_name='Not A Staff Applicant', qualified_for='Affirmative')
        self.assertNotContains(self.c.get('/vpsea/ranking/?type=Staff'),
                               'Not A Staff Applicant')
