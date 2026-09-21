"""Duplicate benefits and repeated award numbers, refused by the database.

Statement of the Problem #7 names duplicate benefits as a core problem to
solve. It was checked in one advisory rule for one programme, which meant a
second award could always be written. These cases assert the refusal happens
in the database, where no view can forget it.
"""

from django.apps import apps as installed_apps
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from importlib import import_module
from io import StringIO

from api.models import (
    Application, ImportedScholar, Scholarship, ScholarshipLinkRequest,
    StudentProfile, SystemSettings, User,
)


class AwardIntegrityTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        for stype, name in (('Academic', 'Academic Scholarship'),
                            ('TDP', 'TDP Scholarship'),
                            ('CHED', 'CHED Merit')):
            Scholarship.objects.create(
                name=name, type=stype, category='application',
                description='x', eligibility='x', requirements=[])
        self.student = self._student('2026-0001')
        self.other = self._student('2026-0002')

    def _student(self, student_id):
        """A verified student with a profile."""
        user = User.objects.create_user(
            username=f'{student_id}@bipsu.edu.ph',
            email=f'{student_id}@bipsu.edu.ph', password='pw',
            first_name='Test', last_name=student_id, role='student')
        return StudentProfile.objects.create(
            user=user, student_id=student_id, course='BSCS', year_level=2)

    def _award(self, student, stype, status='Approved', award_number='',
               term='26-1'):
        """One award, written the way the office writes them."""
        return Application.objects.create(
            student=student, scholarship=Scholarship.objects.get(type=stype),
            status=status, term_label=term, award_number=award_number)

    def test_a_second_benefit_is_recorded_rather_than_refused(self):
        """The office has to be able to see a duplicate to act on it.

        A student who really does hold a DOST award and a CHED award is the
        case this system exists to surface. A database that refused the
        second row could not show the office the first thing about it.
        """
        self._award(self.student, 'CHED')
        second = self._award(self.student, 'TDP')
        self.assertEqual(
            Application.objects.filter(
                student=self.student, status='Approved').count(), 2)
        self.assertTrue(second.pk)

    def test_a_second_benefit_names_the_award_it_duplicates(self):
        first = self._award(self.student, 'CHED')
        second = self._award(self.student, 'TDP')
        self.assertEqual([a.pk for a in second.conflicts_with()], [first.pk])

    def test_a_single_award_conflicts_with_nothing(self):
        self.assertFalse(self._award(self.student, 'CHED').conflicts_with())

    def test_an_internal_scholarship_is_not_a_duplicate_benefit(self):
        self._award(self.student, 'Academic')
        national = self._award(self.student, 'CHED')
        self.assertFalse(
            national.conflicts_with(),
            'an internal BiPSU scholarship was counted as a national grant')

    def test_a_pending_application_is_not_a_conflict_yet(self):
        self._award(self.student, 'CHED', status='Pending Validation')
        self.assertFalse(self._award(self.student, 'TDP').conflicts_with())

    def test_an_award_in_another_term_is_not_a_conflict(self):
        self._award(self.student, 'CHED', term='26-1')
        later = self._award(self.student, 'TDP', term='26-2')
        self.assertFalse(later.conflicts_with())

    def test_another_students_award_is_not_a_conflict(self):
        self._award(self.other, 'CHED')
        self.assertFalse(self._award(self.student, 'TDP').conflicts_with())

    def test_an_award_number_cannot_be_issued_twice_for_one_programme_term(self):
        self._award(self.student, 'CHED', award_number='CHED-2026-0001')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._award(self.other, 'CHED', award_number='CHED-2026-0001')

    def test_a_blank_award_number_is_not_treated_as_a_duplicate(self):
        self._award(self.student, 'CHED')
        self._award(self.other, 'CHED')
        self.assertEqual(
            Application.objects.filter(award_number='').count(), 2)

    def test_the_same_award_number_may_recur_in_a_later_term(self):
        self._award(self.student, 'CHED', award_number='CHED-2026-0001',
                    term='26-1')
        self._award(self.student, 'CHED', award_number='CHED-2026-0001',
                    term='26-2')
        self.assertEqual(
            Application.objects.filter(
                award_number='CHED-2026-0001').count(), 2)

    def test_an_imported_list_cannot_carry_one_award_number_twice(self):
        ImportedScholar.objects.create(
            scholarship_type='CHED', term_label='26-1', last_name='Santos',
            award_number='CHED-2026-0100')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ImportedScholar.objects.create(
                scholarship_type='CHED', term_label='26-1', last_name='Cruz',
                award_number='CHED-2026-0100')

    def test_two_students_may_both_claim_one_number_until_one_is_approved(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        def declaration(student, status):
            """A declaration of an award granted elsewhere."""
            return ScholarshipLinkRequest.objects.create(
                student=student, scholarship_type='CHED', status=status,
                term_label='26-1', award_number='CHED-2026-0200',
                proof_document=SimpleUploadedFile(
                    'proof.pdf', b'%PDF-1.4', content_type='application/pdf'))

        declaration(self.student, 'Pending')
        declaration(self.other, 'Pending')
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 2)

        first = ScholarshipLinkRequest.objects.first()
        first.status = 'Approved'
        first.save()
        second = ScholarshipLinkRequest.objects.exclude(pk=first.pk).get()
        second.status = 'Approved'
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.save()


class DuplicateReportTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        Scholarship.objects.create(
            name='CHED Merit', type='CHED', category='application',
            description='x', eligibility='x', requirements=[])

    def test_a_clean_database_reports_nothing_to_settle(self):
        out = StringIO()
        call_command('find_duplicate_awards', stdout=out)
        self.assertIn('no duplicate benefits', out.getvalue())

    def _a_student_holding(self, *types, student_id='2026-0009'):
        """One student with an approved award in each named programme."""
        user = User.objects.create_user(
            username=f'{student_id}@bipsu.edu.ph',
            email=f'{student_id}@bipsu.edu.ph', password='pw', role='student')
        student = StudentProfile.objects.create(
            user=user, student_id=student_id, course='BSCS', year_level=2)
        for stype in types:
            programme = Scholarship.objects.filter(type=stype).first()
            if programme is None:
                programme = Scholarship.objects.create(
                    name=f'{stype} Scholarship', type=stype,
                    category='application', description='x', eligibility='x',
                    requirements=[])
            Application.objects.create(
                student=student, scholarship=programme, status='Approved',
                term_label='26-1')
        return student

    def test_two_national_grants_in_one_term_are_reported(self):
        self._a_student_holding('CHED', 'TDP')

        out = StringIO()
        call_command('find_duplicate_awards', stdout=out)
        printed = out.getvalue()
        self.assertIn('duplicate benefits', printed)
        self.assertIn('CHED, TDP', printed)

    def test_an_internal_scholarship_beside_a_grant_is_not_reported(self):
        self._a_student_holding('CHED', 'Academic')

        out = StringIO()
        call_command('find_duplicate_awards', stdout=out)
        self.assertIn('no duplicate benefits', out.getvalue())

    def test_the_fail_flag_makes_it_usable_as_a_deploy_gate(self):
        from django.core.management.base import CommandError

        self._a_student_holding('CHED', 'TDP', student_id='2026-0010')
        with self.assertRaises(CommandError):
            call_command('find_duplicate_awards', '--fail', stdout=StringIO())


class MigrationGuardTest(TestCase):

    CONSTRAINTS = (
        'one_award_number_per_programme_term',
        'one_imported_award_number_per_term',
        'one_approved_link_award_number_per_term',
    )

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.ched = Scholarship.objects.create(
            name='CHED Merit', type='CHED', category='application',
            description='x', eligibility='x', requirements=[])
        self._drop_award_number_constraints()

    def _drop_award_number_constraints(self):
        with connection.cursor() as cursor:
            for name in self.CONSTRAINTS:
                cursor.execute(f'DROP INDEX {name}')

    def _guard(self):
        module = import_module('api.migrations.0096_award_integrity')
        module.refuse_duplicate_award_numbers(installed_apps, None)

    def _student(self, student_id):
        user = User.objects.create_user(
            username=f'{student_id}@bipsu.edu.ph',
            email=f'{student_id}@bipsu.edu.ph', password='pw', role='student')
        return StudentProfile.objects.create(
            user=user, student_id=student_id, course='BSCS', year_level=2)

    def _awarded(self, student_id, number, programme=None):
        return Application.objects.create(
            student=self._student(student_id),
            scholarship=programme or self.ched,
            status='Approved', term_label='26-1', award_number=number)

    def test_a_clean_database_lets_the_migration_through(self):
        self._awarded('2026-0001', 'CHED-1')
        self._guard()

    def test_the_refusal_names_the_rows_it_found(self):
        self._awarded('2026-0002', 'CHED-2')
        self._awarded('2026-0003', 'CHED-2')

        with self.assertRaises(RuntimeError) as refused:
            self._guard()
        message = str(refused.exception)
        self.assertIn('CHED Merit', message)
        self.assertIn('CHED-2', message)
        self.assertIn('recorded 2 times', message)

    def test_a_blank_term_is_named_rather_than_left_out(self):
        self._awarded('2026-0004', 'CHED-3')
        self._awarded('2026-0005', 'CHED-3')
        Application.objects.update(term_label='', school_year='', semester='')

        with self.assertRaises(RuntimeError) as refused:
            self._guard()
        self.assertIn('(blank)', str(refused.exception))

    def test_two_different_people_under_one_imported_number_are_found(self):
        for last_name, first_name in (('Dela Cruz', 'Juan'),
                                      ('Bagasbas', 'Maria')):
            ImportedScholar.objects.create(
                last_name=last_name, first_name=first_name,
                scholarship_type='CHED', term_label='26-1',
                award_number='IMP-1')

        with self.assertRaises(RuntimeError) as refused:
            self._guard()
        message = str(refused.exception)
        self.assertIn('ImportedScholar', message)
        self.assertIn('IMP-1', message)
        self.assertIn('recorded 2 times', message)

        out = StringIO()
        call_command('find_duplicate_awards', stdout=out)
        self.assertIn('repeated award numbers in ImportedScholar',
                      out.getvalue())

    def test_a_wholesale_clash_is_cut_short_with_a_count(self):
        module = import_module('api.migrations.0096_award_integrity')
        over = module.CLASH_LIMIT + 3
        ImportedScholar.objects.bulk_create([
            ImportedScholar(last_name=f'Scholar{n}', scholarship_type='CHED',
                            term_label='26-1', award_number=f'IMP-{n}')
            for n in range(over) for _ in range(2)
        ])

        with self.assertRaises(RuntimeError) as refused:
            self._guard()
        message = str(refused.exception)
        self.assertIn('... and 3 more', message)
        self.assertEqual(message.count('recorded 2 times'), module.CLASH_LIMIT)

    def test_two_programmes_of_one_type_are_not_a_repeated_number(self):
        tulong_dunong = Scholarship.objects.create(
            name='CHED Tulong Dunong', type='CHED', category='application',
            description='x', eligibility='x', requirements=[])
        self._awarded('2026-0006', 'CHED-4')
        self._awarded('2026-0007', 'CHED-4', programme=tulong_dunong)

        out = StringIO()
        call_command('find_duplicate_awards', stdout=out)
        self.assertIn('no repeated award numbers', out.getvalue())
        self._guard()

    def test_the_report_names_the_programme_the_number_repeats_in(self):
        self._awarded('2026-0008', 'CHED-5')
        self._awarded('2026-0009', 'CHED-5')

        out = StringIO()
        call_command('find_duplicate_awards', stdout=out)
        printed = out.getvalue()
        self.assertIn('repeated award numbers in Application', printed)
        self.assertIn('CHED Merit', printed)
        self.assertIn('CHED-5', printed)
