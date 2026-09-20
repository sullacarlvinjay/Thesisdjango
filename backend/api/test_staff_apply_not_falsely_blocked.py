from django.test import Client, TestCase

from api.models import ApplicantRecord, Scholarship, SystemSettings, User


BLOCKED = 'You already have a Staff Scholarship application'


class StaffApplyGuardTest(TestCase):
    """The apply page must refuse only an application filed for the term in play.

    Every write path stamps an ``ApplicantRecord`` with the term it was filed
    in. A guard that matched on email alone therefore kept finding last
    semester's record and told an employee they had already applied when, for
    the open term, they had not.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})
        Scholarship.objects.create(
            name='Staff Scholarship', type='Staff', category='application',
            description='x', eligibility='x', requirements=[],
            accepting_applications=True)
        self.user = User.objects.create_user(
            username='faculty@bipsu.edu.ph', email='faculty@bipsu.edu.ph',
            password='pw', first_name='Rosa', last_name='Delgado',
            role='nsu_staff')
        self.c = Client()
        self.assertTrue(self.c.login(email='faculty@bipsu.edu.ph', password='pw'))

    def _record(self, **overrides):
        fields = dict(
            full_name='Rosa Delgado', email='faculty@bipsu.edu.ph',
            qualified_for='Staff', status='Pending Validation',
            course='—', year_level=1, is_nsu_staff=True,
            school_year='2026-2027', semester='2nd Semester',
            term_label='26-2',
        )
        fields.update(overrides)
        return ApplicantRecord.objects.create(**fields)

    def _apply_page(self):
        return self.c.get('/nsu-staff/apply/')

    def test_an_employee_who_has_never_applied_is_not_blocked(self):
        page = self._apply_page().content.decode()
        self.assertNotIn(BLOCKED, page)

    def test_last_terms_application_does_not_block_this_terms(self):
        self._record(school_year='2025-2026', semester='1st Semester',
                     term_label='25-1')
        page = self._apply_page().content.decode()
        self.assertNotIn(
            BLOCKED, page,
            'a record from 25-1 blocked an application for 26-2')

    def test_a_dependents_record_does_not_block_the_employee(self):
        self._record(full_name='Child Delgado', is_nsu_staff=False,
                     is_nsu_dependent=True, staff_employee_id='E-1001')
        page = self._apply_page().content.decode()
        self.assertNotIn(
            BLOCKED, page,
            "a dependent's record blocked the employee's own application")

    def test_a_rejected_application_does_not_block_a_resubmission(self):
        self._record(status='Rejected')
        page = self._apply_page().content.decode()
        self.assertNotIn(BLOCKED, page)

    def test_a_pending_application_for_this_term_still_blocks(self):
        self._record(status='Pending Validation')
        page = self._apply_page().content.decode()
        self.assertIn(
            BLOCKED, page,
            'the guard stopped refusing a genuine duplicate for the open term')

    def test_an_approved_application_for_this_term_still_blocks(self):
        self._record(status='Approved')
        page = self._apply_page().content.decode()
        self.assertIn(BLOCKED, page)


class StaffNavApplyLinkTest(TestCase):
    """The sidebar's Apply link must agree with the guard behind it.

    Hiding the link on any record ever filed, while the guard admits one per
    term, would leave the link missing in a term the employee may still apply
    for.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': '26-2',
                            'active_semester': '2nd Semester'})
        User.objects.create_user(
            username='faculty@bipsu.edu.ph', email='faculty@bipsu.edu.ph',
            password='pw', first_name='Rosa', last_name='Delgado',
            role='nsu_staff')
        self.c = Client()
        self.assertTrue(self.c.login(email='faculty@bipsu.edu.ph', password='pw'))

    def _dashboard(self):
        return self.c.get('/nsu-staff/').content.decode()

    def test_the_link_shows_when_nothing_has_been_filed(self):
        self.assertIn('/nsu-staff/apply/', self._dashboard())

    def test_the_link_returns_in_a_term_with_no_application(self):
        ApplicantRecord.objects.create(
            full_name='Rosa Delgado', email='faculty@bipsu.edu.ph',
            qualified_for='Staff', status='Approved', course='—', year_level=1,
            is_nsu_staff=True, school_year='2025-2026',
            semester='1st Semester', term_label='25-1')
        self.assertIn(
            '/nsu-staff/apply/', self._dashboard(),
            'last term\'s award kept the Apply link hidden in a new term')

    def test_the_link_hides_once_this_term_has_an_application(self):
        ApplicantRecord.objects.create(
            full_name='Rosa Delgado', email='faculty@bipsu.edu.ph',
            qualified_for='Staff', status='Pending Validation', course='—',
            year_level=1, is_nsu_staff=True, school_year='2026-2027',
            semester='2nd Semester', term_label='26-2')
        self.assertNotIn('/nsu-staff/apply/', self._dashboard())
