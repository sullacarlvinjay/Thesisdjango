"""A decision is made once.

The review screen used to write whatever status was posted, every time it was
posted, taking no notice of what the application already said. An approval could
be turned into a rejection days later — the applicant left holding a
notification that no longer matched their record, and nothing anywhere saying
who changed it or why. These tests hold the SDSO's applications page to one
decision per application.
"""
import datetime

from django.test import Client, TestCase

from api.models import (
    AffirmativeStaffApplication, Application, Notification, Scholarship,
    StudentProfile, SystemSettings, User,
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
