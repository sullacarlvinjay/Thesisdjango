"""A decision is made once.

Both review offices used to write whatever status was posted, every time it was
posted, taking no notice of what the application already said. An approval could
be turned into a rejection days later — the applicant left holding a
notification that no longer matched their record, and nothing anywhere saying
who changed it or why. These tests hold both screens to one decision per
application: SDSO's applications page and UniFAST's TES review.
"""
import datetime

from django.test import Client, TestCase

from api.models import (
    AffirmativeStaffApplication, Application, Notification, Scholarship,
    StudentProfile, SystemSettings, TESApplication, User,
)


def make_student(email, sid, last='Cruz'):
    user = User.objects.create_user(
        username=email, email=email, password='pw',
        first_name='Test', last_name=last, role='student',
    )
    return StudentProfile.objects.create(
        user=user, student_id=sid, course='BSCS', year_level=2, gwa=1.4)


class SDSODecidesOnceTest(TestCase):
    """The SDSO applications screen — Academic, Affirmative and Staff tabs."""

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        self.scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[],
        )
        User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='pw', role='vpsea',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='sdso@bipsu.edu.ph', password='pw'))
        self.student = make_student('applicant@bipsu.edu.ph', '2024-0001')

    def _application(self, status='Pending Validation'):
        return Application.objects.create(
            student=self.student, scholarship=self.scholarship,
            status=status, term_label='26-1',
        )

    def _decide(self, app, status, remarks='', tab='academic'):
        return self.c.post('/vpsea/affirmative/', {
            'app_id': app.id, 'status': status, 'remarks': remarks, 'tab': tab,
        })

    def _affirmative(self, status='Pending Validation', qualified_for='Affirmative'):
        return AffirmativeStaffApplication.objects.create(
            full_name='Juan Dela Cruz', email='juan@bipsu.edu.ph',
            contact_number='09171234567', date_of_birth=datetime.date(2004, 5, 1),
            course='BSIT', qualified_for=qualified_for, status=status,
        )

    def _decoded(self, response):
        """The redirect target, readable — the reason is URL-quoted into it."""
        return response['Location'].replace('%20', ' ').replace('+', ' ')

    # ── the first decision still works ──────────────────────────────────────

    def test_a_waiting_application_can_be_decided(self):
        app = self._application()
        self._decide(app, 'Approved', 'Congratulations.')

        app.refresh_from_db()
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.remarks, 'Congratulations.')
        self.assertEqual(Notification.objects.filter(student=self.student).count(), 1)

    # ── and only the first ──────────────────────────────────────────────────

    def test_an_approval_cannot_be_turned_into_a_rejection(self):
        app = self._application('Approved')
        r = self._decide(app, 'Rejected', 'Changed my mind.')

        app.refresh_from_db()
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.remarks, '')
        self.assertIn('error=', r['Location'])

    def test_a_rejection_cannot_be_turned_into_an_approval(self):
        app = self._application('Rejected')
        self._decide(app, 'Approved')

        app.refresh_from_db()
        self.assertEqual(app.status, 'Rejected')

    def test_an_application_sent_back_is_decided_too(self):
        """Send Back is a decision like the other two, so it locks like them."""
        app = self._application('Needs Revision')
        self._decide(app, 'Approved')

        app.refresh_from_db()
        self.assertEqual(app.status, 'Needs Revision')

    def test_the_same_decision_posted_twice_announces_it_once(self):
        """A double-click on Approve must not tell the applicant twice."""
        app = self._application()
        self._decide(app, 'Approved', 'Congratulations.')
        self._decide(app, 'Approved', 'Congratulations.')

        self.assertEqual(Notification.objects.filter(student=self.student).count(), 1)

    def test_the_refusal_names_the_application_and_what_it_already_says(self):
        app = self._application('Approved')
        target = self._decoded(self._decide(app, 'Rejected'))

        self.assertIn(f'APP-{app.id:07d}', target)
        self.assertIn('Approved', target)

    # ── the affirmative and staff tabs follow the same rule ─────────────────

    def test_a_decided_affirmative_application_is_not_decided_again(self):
        aff = self._affirmative('Approved')
        r = self._decide(aff, 'Rejected', 'No.', tab='affirmative')

        aff.refresh_from_db()
        self.assertEqual(aff.status, 'Approved')
        self.assertIn('error=', r['Location'])

    def test_a_decided_staff_application_is_not_decided_again(self):
        staff = self._affirmative('Rejected', qualified_for='Staff')
        self._decide(staff, 'Approved', tab='staff')

        staff.refresh_from_db()
        self.assertEqual(staff.status, 'Rejected')

    def test_approving_an_affirmative_application_twice_makes_one_account(self):
        """Approval creates the applicant's account — twice would collide."""
        aff = self._affirmative()
        self._decide(aff, 'Approved', tab='affirmative')
        self._decide(aff, 'Approved', tab='affirmative')

        self.assertEqual(User.objects.filter(email='juan@bipsu.edu.ph').count(), 1)

    # ── what the screen shows ───────────────────────────────────────────────

    def test_the_button_is_named_for_what_it_does(self):
        self._application()
        r = self.c.get('/vpsea/affirmative/?tab=academic')

        self.assertContains(r, 'Send Back')
        self.assertNotContains(r, 'Request Revision')

    def test_a_decided_row_carries_its_decision_to_the_modal(self):
        """The modal hides the buttons off these, so they have to reach it."""
        self._application('Approved')
        r = self.c.get('/vpsea/affirmative/?tab=academic')

        self.assertContains(r, 'data-status="Approved"')
        self.assertContains(r, 'id="acadDecided"')

    def test_a_refusal_is_shown_rather_than_swallowed(self):
        r = self.c.get('/vpsea/affirmative/?tab=academic&error=Already+decided.')
        self.assertContains(r, 'Already decided.')


class UniFASTDecidesOnceTest(TestCase):
    """UniFAST's TES review — the same rule, with room for CHED's paperwork."""

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1', active_semester='1st Semester')
        Scholarship.objects.create(
            name='Tertiary Education Subsidy', type='TES', category='application',
            description='x', eligibility='x', requirements=[],
        )
        User.objects.create_user(
            username='unifast@bipsu.edu.ph', email='unifast@bipsu.edu.ph',
            password='pw', role='unifast',
        )
        self.c = Client()
        self.assertTrue(self.c.login(email='unifast@bipsu.edu.ph', password='pw'))
        self.student = make_student('tes@bipsu.edu.ph', '2024-0002')

    def _tes(self, status='Pending'):
        return TESApplication.objects.create(student=self.student, status=status)

    def _review(self, app, **post):
        return self.c.post(f'/unifast/tes-applications/{app.pk}/review/', post)

    def test_a_waiting_application_can_be_decided(self):
        app = self._tes()
        self._review(app, status='Approved', remarks='Awarded.', award_number='TES-2026-1')

        app.refresh_from_db()
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(Notification.objects.filter(student=self.student).count(), 1)

    def test_an_approval_cannot_be_turned_into_a_rejection(self):
        app = self._tes('Approved')
        r = self._review(app, status='Rejected', remarks='No.')

        app.refresh_from_db()
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.remarks, '')
        self.assertIn('error=', r['Location'])

    def test_the_award_number_can_still_be_corrected_afterwards(self):
        """CHED issues it after the decision and the billing report is built on
        it, so a typo there must not need the decision reopened."""
        app = self._tes()
        self._review(app, status='Approved', award_number='TES-2026-0O1')
        self._review(app, status='Approved', award_number='TES-2026-001')

        app.refresh_from_db()
        self.assertEqual(app.status, 'Approved')
        self.assertEqual(app.award_number, 'TES-2026-001')
        # The correction is bookkeeping, not a second announcement.
        self.assertEqual(Notification.objects.filter(student=self.student).count(), 1)

    def test_the_award_number_correction_reaches_the_award_itself(self):
        app = self._tes()
        self._review(app, status='Approved', award_number='TES-2026-0O1')
        self._review(app, status='Approved', award_number='TES-2026-001')

        award = Application.objects.get(student=self.student, scholarship__type='TES')
        self.assertEqual(award.award_number, 'TES-2026-001')

    def test_the_list_endpoint_will_not_overwrite_a_decision_either(self):
        app = self._tes('Approved')
        self.c.post('/unifast/tes-applications/', {
            'app_id': app.id, 'status': 'Rejected', 'remarks': 'No.',
        })

        app.refresh_from_db()
        self.assertEqual(app.status, 'Approved')

    def test_a_decided_application_offers_no_status_menu(self):
        self._tes('Approved')
        r = self.c.get('/unifast/tes-applications/')

        self.assertNotContains(r, '<select name="status"')
        self.assertContains(r, 'name="award_number"')

    def test_a_waiting_application_still_offers_one(self):
        self._tes()
        r = self.c.get('/unifast/tes-applications/')

        self.assertContains(r, '<select name="status"')
