"""The term an account registered in, for employees as well as students.

The office's Recently Decided table reported a term for students and a dash for
every BiPSU Staff row. The column read ``student_profile.term_display``, which
an employee account has none of — and behind that, ``StaffProfile`` was not
term-stamped at all, so there was nothing for a corrected template to read.

These register through the real forms and then read the office's own page,
because a template that names the right attribute still shows a dash when the
attribute was never filled.
"""

from django.test import Client, TestCase

from api.models import StaffProfile, StudentProfile, SystemSettings, User


class ARegistrationRecordsItsTermTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')

    def test_a_student_profile_is_stamped_with_the_active_term(self):
        student = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph',
            password='pw', role='student')
        profile = StudentProfile.objects.create(user=student)
        self.assertEqual(profile.term_label, '26-1')
        self.assertEqual(profile.term_display, '2026-2027 1st Semester')

    def test_an_employee_profile_is_stamped_the_same_way(self):
        staff = User.objects.create_user(
            username='e@bipsu.edu.ph', email='e@bipsu.edu.ph',
            password='pw', role='nsu_staff')
        profile = StaffProfile.objects.create(user=staff)
        self.assertEqual(profile.term_label, '26-1')
        self.assertEqual(profile.term_display, '2026-2027 1st Semester')

    def test_the_stamp_follows_the_term_the_office_has_rolled_to(self):
        row = SystemSettings.objects.get(pk=1)
        row.academic_year = '26-2'
        row.save(update_fields=['academic_year'])
        staff = User.objects.create_user(
            username='later@bipsu.edu.ph', email='later@bipsu.edu.ph',
            password='pw', role='nsu_staff')
        self.assertEqual(
            StaffProfile.objects.create(user=staff).term_display,
            '2026-2027 2nd Semester')


class AStampedTermIsNotOverwrittenTest(TestCase):
    """The backfill in 0102 leans on this.

    It stamps only the rows carrying no term, which is only safe because a row
    that already has one keeps it through every later save.
    """

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.staff = User.objects.create_user(
            username='early@bipsu.edu.ph', email='early@bipsu.edu.ph',
            password='pw', role='nsu_staff')

    def test_a_term_set_by_hand_survives_the_next_save(self):
        profile = StaffProfile.objects.create(
            user=self.staff, term_label='25-2', school_year='2025-2026',
            semester='2nd Semester')
        profile.employee_id = '32-1-213313'
        profile.save()
        profile.refresh_from_db()
        self.assertEqual(profile.term_display, '2025-2026 2nd Semester')


class TheOfficeSeesTheTermOnEveryDecidedRowTest(TestCase):

    def setUp(self):
        from django.utils import timezone

        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.officer = User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='office-pw-1', role='vpsea', is_superuser=True)

        self.staff = User.objects.create_user(
            username='e@bipsu.edu.ph', email='e@bipsu.edu.ph',
            password='pw', role='nsu_staff', first_name='Monette',
            last_name='Bustillo')
        StaffProfile.objects.create(user=self.staff)
        self.staff.verification_status = 'approved'
        self.staff.verified_by = self.officer
        self.staff.verified_at = timezone.now()
        self.staff.save()

        self.client = Client()
        self.client.login(email='sdso@bipsu.edu.ph', password='office-pw-1')

    def decided_student(self):
        """A student account the office has already decided on."""
        from django.utils import timezone

        student = User.objects.create_user(
            username='mahalalil@bipsu.edu.ph', email='mahalalil@bipsu.edu.ph',
            password='pw', role='student', first_name='Mahalalil',
            last_name='Villaflores')
        StudentProfile.objects.create(user=student)
        student.verification_status = 'approved'
        student.verified_by = self.officer
        student.verified_at = timezone.now()
        student.save()
        return student

    def test_each_row_names_its_own_term_not_the_other_row_s(self):
        """The employee registered a term before the student did.

        One of the two profiles is always ``None`` on any given row, which is
        the shape that made the page raise rather than render a dash.
        """
        row = SystemSettings.objects.get(pk=1)
        row.academic_year = '26-2'
        row.save(update_fields=['academic_year'])
        self.decided_student()

        page = self.client.get('/vpsea/accounts/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Monette')
        self.assertContains(page, 'Mahalalil')
        self.assertContains(page, '2026-2027 1st Semester')
        self.assertContains(page, '2026-2027 2nd Semester')

    def test_an_employee_row_names_its_term_rather_than_a_dash(self):
        page = self.client.get('/vpsea/accounts/')
        self.assertContains(page, 'Monette')
        self.assertContains(page, '2026-2027 1st Semester')

    def test_an_employee_registered_before_the_stamp_still_renders(self):
        StaffProfile.objects.filter(user=self.staff).update(
            term_label='', school_year='', semester='')
        page = self.client.get('/vpsea/accounts/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Monette')
