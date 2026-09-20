"""Generate a realistic-sized dataset for load testing.

``seed`` produces a handful of rows to click through. This produces the volume
the office will actually hold, so that pages, reports and rankings are measured
against hundreds of scholars rather than five. Anything that scans a table
without a limit, or issues a query per row, shows up here and nowhere else.

Usage::

    python manage.py seed_load --students 500 --staff 60
    python manage.py seed_load --students 2000 --clear

Rows are written with ``bulk_create`` in batches, so the command itself is not
the slow part of whatever you are measuring.
"""

import datetime
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from api.catalogue import ensure_scholarships
from api.models import (
    ApplicantRecord, Application, Scholarship, StudentProfile, SystemSettings,
    User,
)

FIRST_NAMES = [
    'Maria', 'Jose', 'Ana', 'Juan', 'Rosa', 'Pedro', 'Grace', 'Mark',
    'Liza', 'Noel', 'Cristina', 'Ramon', 'Divina', 'Arnel', 'Jocelyn',
    'Ricardo', 'Elena', 'Fernando', 'Teresa', 'Manuel',
]
LAST_NAMES = [
    'Santos', 'Reyes', 'Cruz', 'Bautista', 'Ocampo', 'Garcia', 'Mendoza',
    'Torres', 'Flores', 'Villanueva', 'Ramos', 'Aquino', 'Castillo',
    'Salazar', 'Delgado', 'Enriquez', 'Gabriel', 'Hernandez',
]
COURSES = [
    'BS Computer Science', 'BS Information Technology', 'BS Education',
    'BS Agriculture', 'BS Nursing', 'BS Criminology', 'BS Accountancy',
    'BS Civil Engineering', 'BS Fisheries', 'BS Hospitality Management',
]
MUNICIPALITIES = [
    'Naval', 'Biliran', 'Cabucgayan', 'Caibiran', 'Culaba', 'Kawayan',
    'Maripipi', 'Almeria',
]
GENDERS = ['Male', 'Female']
STATUSES = ['Approved', 'Pending Validation', 'Rejected', 'Needs Revision']


class Command(BaseCommand):
    help = 'Generate a large, realistic dataset for load testing.'

    def add_arguments(self, parser):
        parser.add_argument('--students', type=int, default=500,
                            help='student accounts with profiles (default 500)')
        parser.add_argument('--staff', type=int, default=50,
                            help='employee applicant records (default 50)')
        parser.add_argument('--terms', type=int, default=3,
                            help='how many past terms to spread records over')
        parser.add_argument('--seed', type=int, default=20260920,
                            help='random seed, so runs are reproducible')
        parser.add_argument('--clear', action='store_true',
                            help='delete previously generated rows first')

    def handle(self, *args, **options):
        random.seed(options['seed'])
        SystemSettings.objects.get_or_create(pk=1)
        ensure_scholarships()

        if options['clear']:
            self._clear()

        terms = self._terms(options['terms'])
        students = self._students(options['students'])
        self._applications(students, terms)
        self._staff_records(options['staff'], terms)

        self.stdout.write(self.style.SUCCESS(
            f"generated {options['students']} students, "
            f"{options['staff']} employee records across {len(terms)} terms"))
        self.stdout.write(
            'Measure with: python manage.py test api.test_report_volume')

    def _clear(self):
        self.stdout.write('clearing previously generated rows...')
        generated = User.objects.filter(email__endswith='@load.bipsu.edu.ph')
        Application.objects.filter(student__user__in=generated).delete()
        StudentProfile.objects.filter(user__in=generated).delete()
        generated.delete()
        ApplicantRecord.objects.filter(
            email__endswith='@load.bipsu.edu.ph').delete()

    def _terms(self, count):
        settings_obj = SystemSettings.objects.get(pk=1)
        labels = [settings_obj.academic_year]
        yy, sem = settings_obj.academic_year.split('-')
        yy, sem = int(yy), int(sem)
        for _ in range(count - 1):
            sem -= 1
            if sem == 0:
                sem, yy = 2, yy - 1
            labels.append(f'{yy}-{sem}')
        return labels

    @transaction.atomic
    def _students(self, count):
        self.stdout.write(f'creating {count} student accounts...')
        existing = set(User.objects.values_list('email', flat=True))
        accounts = []
        for n in range(count):
            email = f'student{n:05d}@load.bipsu.edu.ph'
            if email in existing:
                continue
            accounts.append(User(
                username=email, email=email,
                first_name=random.choice(FIRST_NAMES),
                last_name=random.choice(LAST_NAMES),
                role='student', verification_status='approved',
                is_active=True))
        User.objects.bulk_create(accounts, batch_size=500)

        made = list(User.objects.filter(
            email__endswith='@load.bipsu.edu.ph', role='student'))
        have = set(StudentProfile.objects.filter(
            user__in=made).values_list('user_id', flat=True))
        profiles = [
            StudentProfile(
                user=account,
                student_id=f'2024-{10000 + n:05d}',
                course=random.choice(COURSES),
                year_level=random.randint(1, 4),
                gwa=round(random.uniform(1.0, 3.0), 2),
                contact_number=f'+63 917 {random.randint(1000000, 9999999)}',
                municipality=random.choice(MUNICIPALITIES),
                province='Biliran',
                barangay=f'Barangay {random.randint(1, 40)}',
                date_of_birth=datetime.date(
                    random.randint(2000, 2006), random.randint(1, 12),
                    random.randint(1, 28)),
                gender=random.choice(GENDERS),
                family_income=random.randrange(40000, 400000, 5000),
            )
            for n, account in enumerate(made) if account.id not in have
        ]
        StudentProfile.objects.bulk_create(profiles, batch_size=500)
        return list(StudentProfile.objects.filter(user__in=made))

    def _applications(self, profiles, terms):
        self.stdout.write(f'creating applications for {len(profiles)} students...')
        catalogue = list(Scholarship.objects.filter(is_active=True))
        if not catalogue:
            return
        rows = []
        for profile in profiles:
            for label in random.sample(terms, k=min(len(terms),
                                                    random.randint(1, 2))):
                parsed = SystemSettings.parse_label(label)
                rows.append(Application(
                    student=profile,
                    scholarship=random.choice(catalogue),
                    status=random.choices(
                        STATUSES, weights=[6, 2, 1, 1], k=1)[0],
                    remarks='',
                    term_label=label,
                    school_year=parsed['sy'],
                    semester=parsed['semester'],
                ))
        Application.objects.bulk_create(rows, batch_size=500,
                                        ignore_conflicts=True)

    def _staff_records(self, count, terms):
        self.stdout.write(f'creating {count} employee records...')
        rows = []
        for n in range(count):
            label = random.choice(terms)
            parsed = SystemSettings.parse_label(label)
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            rows.append(ApplicantRecord(
                full_name=f'{first} {last}',
                email=f'employee{n:04d}@load.bipsu.edu.ph',
                qualified_for='Staff',
                status=random.choices(STATUSES, weights=[6, 3, 1, 1], k=1)[0],
                term_label=label,
                school_year=parsed['sy'],
                semester=parsed['semester'],
            ))
        for row in rows:
            row.save()
