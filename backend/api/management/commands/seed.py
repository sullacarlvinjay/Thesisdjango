from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import (
    StudentProfile, Scholarship, Application, Notification,
    Announcement,
    ActivityLog, SystemSettings, ImportedScholar,
    AffirmativeStaffApplication,
)
from api.catalogue import ensure_scholarships
from rest_framework.authtoken.models import Token
import datetime

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with initial data matching the mock data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')

        # System settings
        SystemSettings.objects.get_or_create(pk=1)

        # Super admin
        super_user, _ = User.objects.get_or_create(
            email='it@bipsu.edu.ph',
            defaults={'username': 'it@bipsu.edu.ph', 'first_name': 'IT', 'last_name': 'Admin', 'role': 'super', 'is_staff': True, 'is_superuser': True}
        )
        super_user.set_password('admin1234')
        super_user.save()
        Token.objects.get_or_create(user=super_user)

        # VPSEA admin
        vpsea_user, _ = User.objects.get_or_create(
            email='vpsea@bipsu.edu.ph',
            defaults={'username': 'vpsea@bipsu.edu.ph', 'first_name': 'Rosario', 'last_name': 'Bayhon', 'role': 'vpsea'}
        )
        vpsea_user.set_password('vpsea1234')
        vpsea_user.save()
        Token.objects.get_or_create(user=vpsea_user)

        # UniFAST admin
        unifast_user, _ = User.objects.get_or_create(
            email='unifast@bipsu.edu.ph',
            defaults={'username': 'unifast@bipsu.edu.ph', 'first_name': 'Marlon', 'last_name': 'Tabuga', 'role': 'unifast'}
        )
        unifast_user.set_password('unifast1234')
        unifast_user.save()
        Token.objects.get_or_create(user=unifast_user)

        # Student user
        student_user, _ = User.objects.get_or_create(
            email='juan.delacruz@bipsu.edu.ph',
            defaults={'username': 'juan.delacruz@bipsu.edu.ph', 'first_name': 'Juan', 'last_name': 'Dela Cruz', 'role': 'student'}
        )
        student_user.set_password('demo1234')
        student_user.save()
        Token.objects.get_or_create(user=student_user)

        profile, _ = StudentProfile.objects.get_or_create(
            user=student_user,
            defaults={
                'student_id': '2022-00451',
                'course': 'BS Computer Science',
                'year_level': 3,
                'gwa': 1.28,
                'contact_number': '+63 917 555 0142',
                'municipality': 'Naval',
                'province': 'Biliran',
                'date_of_birth': datetime.date(2003, 8, 14),
                'gender': 'Male',
                'family_income': 180000,
                'parent_employment': 'Farmer',
            }
        )

        # Scholarships
        # The catalogue itself lives in api.catalogue, shared with the
        # bootstrap command so a laptop and a deployment cannot end up
        # offering different programmes.
        ensure_scholarships()

        # Applications
        academic = Scholarship.objects.get(type='Academic')
        tdp = Scholarship.objects.get(type='TDP')
        apps_data = [
            {'scholarship': academic, 'status': 'Approved', 'remarks': 'University Scholar', 'submitted_at': datetime.date(2025, 4, 12)},
            {'scholarship': tdp, 'status': 'Pending Validation', 'remarks': 'Awaiting document review', 'submitted_at': datetime.date(2025, 4, 18)},
            {'scholarship': academic, 'status': 'Approved', 'remarks': 'College Scholar', 'submitted_at': datetime.date(2024, 9, 3)},
            {'scholarship': tdp, 'status': 'Needs Revision', 'remarks': 'Re-upload Certificate of Indigency', 'submitted_at': datetime.date(2025, 5, 2)},
        ]
        for a in apps_data:
            if not Application.objects.filter(student=profile, scholarship=a['scholarship'], submitted_at=a['submitted_at']).exists():
                Application.objects.create(student=profile, **a)

        # Notifications
        notifs = [
            {'type': 'success', 'title': 'Application Approved', 'body': 'Your Academic Scholarship application has been approved as University Scholar.'},
            {'type': 'warning', 'title': 'Document Required', 'body': 'Please re-upload your Certificate of Indigency for TDP review.'},
            {'type': 'info', 'title': 'New Scholarship Match', 'body': "You're 90% matched with DOST Merit Scholarship."},
            {'type': 'info', 'title': 'Renewal Reminder', 'body': 'Submit your renewal requirements before May 30, 2025.'},
        ]
        for n in notifs:
            Notification.objects.get_or_create(student=profile, title=n['title'], defaults=n)

        # Announcements
        ann_data = [
            {'title': 'Academic Scholarship A.Y. 2025-2026 Now Open', 'body': 'Applications for the next academic year are now being accepted until June 15.'},
            {'title': 'TDP Liquidation Deadline Extended', 'body': 'UniFAST has extended the liquidation deadline to May 31, 2025.'},
            {'title': 'DOST Scholarship Exam Schedule', 'body': 'The DOST-SEI exam will be held on July 6, 2025.'},
        ]
        for a in ann_data:
            Announcement.objects.get_or_create(title=a['title'], defaults={**a, 'published_by': super_user})

        # Activity logs
        logs_data = [
            (vpsea_user, 'Approved application APP-2025-0021'),
            (unifast_user, 'Released TES Batch 2 funds'),
            (vpsea_user, 'Imported ched_merit_2024.csv'),
            (super_user, 'Updated system settings'),
        ]
        for user, action in logs_data:
            ActivityLog.objects.get_or_create(user=user, action=action)

        # ── Archive test users (one per scholarship type) ──
        archive_students = [
            # (email, first, last, student_id, course, year, gwa, gender, municipality, province, income, extra_profile)
            ('maria.santos@bipsu.edu.ph', 'Maria', 'Santos', '2022-00101', 'BS Education', 2, 1.25, 'Female', 'Caibiran', 'Biliran', 150000, {}),
            ('jose.reyes@bipsu.edu.ph', 'Jose', 'Reyes', '2022-00102', 'BS Agriculture', 3, 1.75, 'Male', 'Almeria', 'Biliran', 90000, {'family_income': 90000}),
            ('ana.garcia@bipsu.edu.ph', 'Ana', 'Garcia', '2022-00103', 'BS Biology', 2, 1.40, 'Female', 'Naval', 'Biliran', 200000, {}),
            ('pedro.lim@bipsu.edu.ph', 'Pedro', 'Lim', '2022-00104', 'BS Nursing', 3, 1.60, 'Male', 'Kawayan', 'Biliran', 250000, {}),
            ('rosa.cruz@bipsu.edu.ph', 'Rosa', 'Cruz', '2022-00105', 'BS Forestry', 1, 1.80, 'Female', 'Culaba', 'Biliran', 120000, {}),
            ('carlo.mendoza@bipsu.edu.ph', 'Carlo', 'Mendoza', '2022-00106', 'BS Physical Education', 2, 2.00, 'Male', 'Biliran', 'Biliran', 180000, {'disability_type': 'Visual Disability'}),
            ('liza.torres@bipsu.edu.ph', 'Liza', 'Torres', '2022-00107', 'BS Criminology', 4, 1.55, 'Female', 'Maripipi', 'Biliran', 160000, {}),
        ]
        scholarship_types = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'GSIS']
        for (email, first, last, sid, course, yr, gwa, gender, mun, prov, income, extra), stype in zip(archive_students, scholarship_types):
            u, _ = User.objects.get_or_create(
                email=email,
                defaults={'username': email, 'first_name': first, 'last_name': last, 'role': 'student'}
            )
            u.set_password('demo1234')
            u.save()
            profile_defaults = {
                'course': course, 'year_level': yr, 'gwa': gwa,
                'gender': gender, 'municipality': mun, 'province': prov,
                'family_income': income,
            }
            profile_defaults.update(extra)
            sp, _ = StudentProfile.objects.get_or_create(user=u, defaults={'student_id': sid, **profile_defaults})
            scholarship = Scholarship.objects.filter(type=stype).first()
            if scholarship and not Application.objects.filter(student=sp, scholarship=scholarship, status='Approved').exists():
                Application.objects.create(
                    student=sp, scholarship=scholarship,
                    status='Approved', remarks='Seeded test scholar',
                    submitted_at=datetime.date(2025, 1, 10),
                )

        # ── Affirmative & Staff archive test applicants ──
        aff_test = [
            {
                'full_name': 'Nena Villanueva', 'email': 'nena.villanueva@test.com',
                'contact_number': '09171234567', 'municipality': 'Naval', 'province': 'Biliran',
                'date_of_birth': datetime.date(2003, 3, 10), 'gender': 'Female',
                'course': 'BS Social Work', 'year_level': 2, 'student_id': '2022-00201',
                'shs_gpa': 88.0, 'suc_exam_score': 72.0, 'is_tes_beneficiary': False,
                'qualified_for': 'Affirmative', 'status': 'Approved',
            },
            {
                'full_name': 'Ramon Dela Pena', 'email': 'ramon.delapena@test.com',
                'contact_number': '09181234567', 'municipality': 'Caibiran', 'province': 'Biliran',
                'date_of_birth': datetime.date(2002, 7, 22), 'gender': 'Male',
                'course': 'BS Accountancy', 'year_level': 3, 'student_id': '2022-00202',
                'is_nsu_staff': False, 'is_nsu_dependent': True,
                'staff_name': 'Ernesto Dela Pena', 'staff_employee_id': 'EMP-0042',
                'relationship_to_staff': 'Son', 'has_baccalaureate': False,
                'qualified_for': 'Staff', 'status': 'Approved',
            },
        ]
        for data in aff_test:
            if not AffirmativeStaffApplication.objects.filter(email=data['email']).exists():
                AffirmativeStaffApplication.objects.create(**data)

        self.stdout.write(self.style.SUCCESS('Database seeded successfully!'))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('  Student:   juan.delacruz@bipsu.edu.ph / demo1234')
        self.stdout.write('  VPSEA:     vpsea@bipsu.edu.ph / vpsea1234')
        self.stdout.write('  UniFAST:   unifast@bipsu.edu.ph / unifast1234')
        self.stdout.write('  Super:     it@bipsu.edu.ph / admin1234')
        self.stdout.write('\nArchive test scholars seeded for: Academic, TDP, DOST, CHED, CoScho, Sports, GSIS, Affirmative, Staff')
