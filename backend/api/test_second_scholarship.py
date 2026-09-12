"""A student may declare more than one scholarship when they register.

Some hold two — CHED and a private foundation, DOST and a local government
grant — and the form asked once. The second award reached the office as an
email, a phone call, or not at all, and the SDSO had no record of it beside the
proof for the first.

Three rules hold this together, and each one is a way it could go wrong:

* **Each declaration is its own link request.** Two awards are two things to
  check, against two sets of records, with two proof documents. Folding them
  into one row would have made the office approve a thing it could only half
  verify.
* **The same programme twice is refused.** Nobody holds CHED twice; that is one
  award typed into two cards. The unique constraint on ``Application`` would
  catch it eventually — at the point where the officer had already said yes.
* **The office is told.** The account queue counts accounts, not declarations,
  so a registration carrying two awards looks exactly like one carrying none
  until somebody opens it.
"""
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.models import (
    ActivityLog, ImportedScholar, Scholarship, ScholarshipLinkRequest,
    StudentProfile, SystemSettings, User,
)
from api.test_registration_payload import a_declared_scholar


def a_proof(name='award.pdf', size=1024):
    return SimpleUploadedFile(name, b'x' * size, content_type='application/pdf')


def two_awards(**overrides):
    """A registration declaring a DOST award and a CHED one.

    Two programmes that really are held together: DOST funds the science
    scholarship, CHED the merit one, and neither agency asks about the other.

    Merged rather than passed through as keywords, so a test can override one of
    the second card's own fields — which is what half the tests below do.
    """
    data = {
        'email': 'juan@gmail.com', 'student_id': '23-0001',
        'scholarship_type': 'DOST', 'proof_document': a_proof('dost.pdf'),
        'has_scholarship_2': 'on', 'scholarship_type_2': 'CHED',
        'award_tier_2': 'Full', 'proof_document_2': a_proof('ched.pdf'),
        'award_number_2': '2026-CHED-0042',
    }
    data.update(overrides)
    return a_declared_scholar(**data)


class TwoDeclarationsAtRegistrationTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.c = Client()

    def test_both_are_recorded_as_their_own_link_request(self):
        self.assertEqual(self.c.post('/register/', two_awards()).status_code, 302)

        requests = ScholarshipLinkRequest.objects.order_by('pk')
        self.assertEqual([r.scholarship_type for r in requests], ['DOST', 'CHED'])
        self.assertTrue(all(r.status == 'Pending' for r in requests))
        # One student, two declarations — not two accounts.
        self.assertEqual(StudentProfile.objects.count(), 1)

    def test_each_keeps_its_own_proof_and_award_number(self):
        """The point of separate rows: the office checks each against the
        document that stands behind it."""
        self.c.post('/register/', two_awards())
        dost = ScholarshipLinkRequest.objects.get(scholarship_type='DOST')
        ched = ScholarshipLinkRequest.objects.get(scholarship_type='CHED')

        self.assertIn('dost', dost.proof_document.name)
        self.assertIn('ched', ched.proof_document.name)
        self.assertEqual(dost.award_number, '')
        self.assertEqual(ched.award_number, '2026-CHED-0042')
        self.assertEqual(ched.award_tier, 'Full')

    def test_a_tier_belongs_to_the_card_that_asked_for_it(self):
        """CHED is the only programme with tiers. Declared on the second card,
        the tier has to land on the second declaration and nowhere else."""
        self.c.post('/register/', two_awards())
        self.assertEqual(
            ScholarshipLinkRequest.objects.get(scholarship_type='DOST').award_tier, '')

    def test_declaring_one_still_works_unchanged(self):
        r = self.c.post('/register/', a_declared_scholar(
            email='ana@gmail.com', student_id='23-0002',
            scholarship_type='DOST', proof_document=a_proof()))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ScholarshipLinkRequest.objects.count(), 1)

    def test_declaring_nothing_still_works_unchanged(self):
        from api.test_registration_payload import a_student
        r = self.c.post('/register/', a_student(email='ben@gmail.com',
                                                student_id='23-0003'))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(ScholarshipLinkRequest.objects.exists())

    def test_three_can_be_declared(self):
        self.c.post('/register/', two_awards(
            has_scholarship_3='on', scholarship_type_3='GSIS',
            proof_document_3=a_proof('gsis.pdf')))
        self.assertEqual(
            set(ScholarshipLinkRequest.objects.values_list('scholarship_type', flat=True)),
            {'DOST', 'CHED', 'GSIS'})


class EachCardIsValidatedOnItsOwnTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.c = Client()

    def test_the_same_programme_twice_is_refused(self):
        """One award typed into two cards, not two awards."""
        r = self.c.post('/register/', two_awards(
            scholarship_type_2='DOST', award_tier_2=''))
        self.assertContains(r, 'twice')
        self.assertFalse(ScholarshipLinkRequest.objects.exists())
        self.assertFalse(User.objects.filter(email='juan@gmail.com').exists())

    def test_a_second_card_with_no_programme_named_is_refused(self):
        r = self.c.post('/register/', two_awards(scholarship_type_2=''))
        self.assertContains(r, 'scholarship 2')
        self.assertFalse(ScholarshipLinkRequest.objects.exists())

    def test_a_second_card_with_no_proof_is_refused(self):
        r = self.c.post('/register/', two_awards(proof_document_2=''))
        self.assertContains(r, 'Proof document is required')
        self.assertFalse(ScholarshipLinkRequest.objects.exists())

    def test_the_error_names_the_card_it_came_from(self):
        """"Say which scholarship you hold" on a form with three of them tells
        the student nothing about which one to fix."""
        r = self.c.post('/register/', two_awards(scholarship_type_2=''))
        self.assertContains(r, '(scholarship 2)')

    def test_the_first_card_says_nothing_about_a_number_that_is_not_shown(self):
        """A student who declared one award should not be sent looking for a
        card number their screen does not have."""
        r = self.c.post('/register/', a_declared_scholar(
            email='ana@gmail.com', student_id='23-0002',
            scholarship_type='', proof_document=a_proof()))
        self.assertContains(r, 'Say which scholarship you already hold,')
        self.assertNotContains(r, '(scholarship 1)')

    def test_one_bad_card_records_neither(self):
        """A registration is one act. Half of it saved is a student who thinks
        they declared two and an office that can see one."""
        self.c.post('/register/', two_awards(scholarship_type_2=''))
        self.assertFalse(ScholarshipLinkRequest.objects.exists())


class TheOfficeIsToldAboutTwoTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.officer = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            role='vpsea')
        self.c = Client()

    def test_the_office_is_emailed(self):
        self.c.post('/register/', two_awards())
        to_office = [m for m in mail.outbox if 'v@bipsu.edu.ph' in m.to]
        self.assertEqual(len(to_office), 1)
        self.assertIn('2 scholarships', to_office[0].subject)

    def test_the_message_names_every_programme(self):
        """A warning that says "more than one" makes the officer open the queue
        to find out what. Naming them lets them start with the records."""
        self.c.post('/register/', two_awards())
        body = [m for m in mail.outbox if 'v@bipsu.edu.ph' in m.to][0].body
        self.assertIn('DOST', body)
        self.assertIn('CHED', body)
        self.assertIn('23-0001', body)

    def test_it_is_logged_whatever_mail_does(self):
        """Delivery is best-effort here as everywhere. A warning nobody can
        find afterwards is a warning that was never given."""
        self.c.post('/register/', two_awards())
        self.assertTrue(ActivityLog.objects.filter(
            action__contains='declared 2 scholarships').exists())

    def test_a_suspended_officer_is_not_emailed(self):
        User.objects.filter(pk=self.officer.pk).update(is_active=False)
        self.c.post('/register/', two_awards())
        self.assertFalse([m for m in mail.outbox if 'v@bipsu.edu.ph' in m.to])

    def test_one_declaration_does_not_raise_the_flag(self):
        """The ordinary case. A warning sent for every registration is a
        warning nobody reads."""
        self.c.post('/register/', a_declared_scholar(
            email='ana@gmail.com', student_id='23-0002',
            scholarship_type='DOST', proof_document=a_proof()))
        self.assertFalse([m for m in mail.outbox if 'v@bipsu.edu.ph' in m.to])
        self.assertFalse(ActivityLog.objects.filter(
            action__contains='scholarships').exists())


class VerifyingAnAccountDecidesEveryDeclarationTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        for name, stype in (('DOST Scholarship', 'DOST'),
                            ('CHED Scholarship', 'CHED')):
            Scholarship.objects.create(
                name=name, type=stype, category='application',
                description='x', eligibility='x', requirements=[])
        self.officer = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            role='vpsea')
        Client().post('/register/', two_awards())
        self.profile = StudentProfile.objects.get()
        self.office = Client()
        self.assertTrue(self.office.login(email='v@bipsu.edu.ph', password='pw'))

    def _decide(self, action='approve', **extra):
        data = {'user_id': self.profile.user_id, 'action': action,
                'message': 'Checked against both award letters'}
        data.update(extra)
        return self.office.post('/vpsea/accounts/', data)

    def test_the_queue_shows_both_cards(self):
        r = self.office.get('/vpsea/accounts/')
        account = r.context['pending'][0]
        self.assertEqual([d.scholarship_type for d in account.declarations],
                         ['DOST', 'CHED'])
        self.assertContains(r, 'declared 2 scholarships')

    def test_each_card_names_the_request_it_belongs_to(self):
        """A single `archive_id` on the form would have offered this student's
        DOST row as the answer to their CHED award."""
        ched = ScholarshipLinkRequest.objects.get(scholarship_type='CHED')
        r = self.office.get('/vpsea/accounts/')
        self.assertContains(r, f'name="award_tier_{ched.pk}"')
        self.assertNotContains(r, 'name="award_tier"')

    def test_verifying_records_both_awards(self):
        from api.models import Application
        self.assertEqual(self._decide().status_code, 302)

        self.assertEqual(
            set(Application.objects.filter(student=self.profile, status='Approved')
                .values_list('scholarship__type', flat=True)),
            {'DOST', 'CHED'})
        self.assertEqual(
            set(ScholarshipLinkRequest.objects.values_list('status', flat=True)),
            {'Approved'})

    def test_rejecting_turns_both_down(self):
        from api.models import Application
        self._decide('reject')
        self.assertEqual(
            set(ScholarshipLinkRequest.objects.values_list('status', flat=True)),
            {'Rejected'})
        self.assertFalse(Application.objects.exists())

    def test_an_imported_row_is_claimed_for_the_card_that_named_it(self):
        row = ImportedScholar.objects.create(
            scholarship_type='CHED', term_label='26-1',
            first_name='Juan', last_name='Dela Cruz', student_id='23-0001')
        ched = ScholarshipLinkRequest.objects.get(scholarship_type='CHED')

        self._decide(**{f'archive_id_{ched.pk}': row.id})

        row.refresh_from_db()
        ched.refresh_from_db()
        self.assertEqual(row.claimed_by_id, self.profile.id)
        self.assertEqual(ched.matched_archive_id, row.id)
        # And the other declaration claimed nothing, because nothing was named.
        self.assertIsNone(ScholarshipLinkRequest.objects
                          .get(scholarship_type='DOST').matched_archive_id)
