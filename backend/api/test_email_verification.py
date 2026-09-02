"""Proving a registrant's address is real, and telling them what was decided.

Two halves of the same gap. Before this, the registration form took any string
with an @ in it, and the SDSO's approval or rejection was announced to whatever
that string was — an address nobody had ever reached, and nobody could tell had
never been reached.
"""
import re
from unittest import mock

from django.core import mail
from django.test import TestCase, Client, override_settings

from api import email_verify
from api.models import User, StudentProfile, SystemSettings


class BrokenBackend:
    """A mail backend that fails the way a refused relay does."""

    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise OSError('connection refused')


class AddressCheckTest(TestCase):
    """The cheap check, on the posted form, before an account exists."""

    def test_a_usable_address_passes(self):
        for address in ('juan@gmail.com', 'a.dela-cruz@bipsu.edu.ph',
                        'student+tag@yahoo.com.ph'):
            self.assertEqual(email_verify.address_error(address), '', address)

    def test_nonsense_is_refused(self):
        for address in ('', '   ', 'juan', 'juan@', '@gmail.com',
                        'juan gmail.com', 'juan@@gmail.com'):
            self.assertNotEqual(email_verify.address_error(address), '',
                                f'{address!r} was accepted')

    def test_the_holes_djangos_validator_leaves_open_are_closed(self):
        """Both are valid addresses and neither is ever a real one on this form.

        Django allowlists 'localhost' and accepts an IP literal. Everything else
        malformed — a dotless domain, a one-letter TLD, a leading hyphen — its
        own validator already refuses, which is why this rule is narrow.
        """
        for address in ('juan@localhost', 'juan@[127.0.0.1]'):
            self.assertIn('not a domain', email_verify.address_error(address),
                          address)

    def test_a_dotless_domain_is_refused_either_way(self):
        for address in ('juan@gmail', 'juan@b', 'juan@example.c'):
            self.assertNotEqual(email_verify.address_error(address), '', address)

    def test_the_message_names_the_address_so_the_typo_is_visible(self):
        self.assertIn('juan@gmial', email_verify.address_error('juan@gmial'))

    def test_an_absurdly_long_address_is_refused(self):
        self.assertNotEqual(email_verify.address_error('a' * 250 + '@gmail.com'), '')


class ConfirmationTokenTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='juan@gmail.com', email='juan@gmail.com', password='pw',
            role='student', email_verified=False)

    def test_a_token_round_trips_to_its_account(self):
        user, reason = email_verify.read_token(email_verify.make_token(self.user))
        self.assertEqual(user, self.user)
        self.assertEqual(reason, '')

    def test_a_tampered_token_is_refused(self):
        token = email_verify.make_token(self.user)
        user, reason = email_verify.read_token(token[:-1] + ('x' if token[-1] != 'x' else 'y'))
        self.assertIsNone(user)
        self.assertEqual(reason, 'invalid')

    def test_an_expired_token_says_so(self):
        token = email_verify.make_token(self.user)
        user, reason = email_verify.read_token(token, max_age=-1)
        self.assertIsNone(user)
        self.assertEqual(reason, 'expired')

    def test_a_link_stops_working_when_the_address_changes(self):
        """It proved somebody reads the old address, which says nothing of the new."""
        token = email_verify.make_token(self.user)
        self.user.email = 'someone.else@gmail.com'
        self.user.save(update_fields=['email'])

        user, reason = email_verify.read_token(token)
        self.assertIsNone(user)
        self.assertEqual(reason, 'stale')

    def test_junk_is_not_an_exception(self):
        self.assertEqual(email_verify.read_token('not-a-token'), (None, 'invalid'))
        self.assertEqual(email_verify.read_token(''), (None, 'invalid'))


class ConfirmationLinkTest(TestCase):
    """A relative path in an email is not a link — nobody can click it."""

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.c = Client()

    def _register(self, **extra):
        self.c.post('/register/', dict({
            'account_type': 'student', 'first_name': 'Juan', 'last_name': 'Cruz',
            'email': 'juan@gmail.com', 'password': 'pw12345',
            'confirm_password': 'pw12345', 'student_id': '23-0001',
            'course': 'BSCS', 'year_level': '1',
        }, **extra))
        return mail.outbox[-1].body

    @override_settings(SITE_URL='https://srms.bipsu.edu.ph')
    def test_site_url_wins_because_a_proxy_can_rewrite_the_host(self):
        self.assertIn('https://srms.bipsu.edu.ph/register/verify/', self._register())

    @override_settings(SITE_URL='')
    def test_without_site_url_the_link_is_built_from_the_request(self):
        """An installation that never set it still sends something clickable."""
        body = self._register()
        self.assertIn('http://testserver/register/verify/', body)

    @override_settings(SITE_URL='')
    def test_a_link_built_from_the_request_still_works(self):
        body = self._register()
        path = re.search(r'/register/verify/[^\s]+/', body).group(0)
        self.c.get(path)
        self.assertTrue(User.objects.get(email='juan@gmail.com').email_verified)


class RegistrationConfirmationTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.c = Client()

    def _register(self, email='juan@gmail.com', student_id='23-0001'):
        return self.c.post('/register/', {
            'account_type': 'student',
            'first_name': 'Juan', 'last_name': 'Cruz',
            'email': email, 'password': 'pw12345', 'confirm_password': 'pw12345',
            'student_id': student_id, 'course': 'BSCS', 'year_level': '1',
        })

    def _link(self):
        """The confirmation path out of the message that was just sent."""
        body = mail.outbox[-1].body
        found = re.search(r'/register/verify/[^\s]+/', body)
        self.assertIsNotNone(found, f'no confirmation link in:\n{body}')
        return found.group(0)

    # ── Registering ─────────────────────────────────────────────────────────

    def test_registering_sends_a_confirmation_link(self):
        self._register()
        user = User.objects.get(email='juan@gmail.com')
        self.assertFalse(user.email_verified)
        self.assertIsNotNone(user.email_confirmation_sent_at)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['juan@gmail.com'])
        self.assertIn('Confirm your email address', message.subject)
        self.assertIn('/register/verify/', message.body)

    def test_a_bad_address_never_becomes_an_account(self):
        r = self._register(email='juan@localhost')
        self.assertEqual(r.status_code, 200)          # back on the form
        self.assertContains(r, 'not a domain')
        self.assertFalse(User.objects.filter(email='juan@localhost').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_a_bad_address_is_not_reported_as_already_registered(self):
        """Two different problems; saying the wrong one sends people in circles."""
        r = self._register(email='juan@')
        self.assertContains(r, 'not a valid email address')
        self.assertNotContains(r, 'Email already registered')

    def test_a_duplicate_address_is_still_refused(self):
        self._register()
        r = self._register(email='juan@gmail.com', student_id='23-0002')
        self.assertContains(r, 'Email already registered')
        self.assertEqual(User.objects.filter(email='juan@gmail.com').count(), 1)

    # ── Confirming ──────────────────────────────────────────────────────────

    def test_opening_the_link_confirms_the_address(self):
        self._register()
        r = self.c.get(self._link())

        self.assertRedirects(r, '/register/received/?confirmed=1',
                             fetch_redirect_response=False)
        self.assertTrue(User.objects.get(email='juan@gmail.com').email_verified)

    def test_confirming_does_not_sign_anyone_in_or_release_them(self):
        """The SDSO's review is still the gate — this only proves the address."""
        self._register()
        self.c.get(self._link())

        user = User.objects.get(email='juan@gmail.com')
        self.assertTrue(user.email_verified)
        self.assertEqual(user.verification_status, 'pending')
        self.assertFalse(user.can_sign_in)
        # And the waiting room is still a waiting room, not a portal.
        r = self.c.get('/register/received/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['waiting'])

    def test_the_page_says_the_address_was_confirmed(self):
        self._register()
        self.c.get(self._link())
        r = self.c.get('/register/received/?confirmed=1')
        self.assertContains(r, 'Email address confirmed')
        self.assertFalse(r.context['confirm_email'])

    def test_an_expired_link_is_explained_rather_than_erroring(self):
        self._register()
        user = User.objects.get(email='juan@gmail.com')
        with mock.patch.object(email_verify, 'CONFIRM_MAX_AGE', -1):
            r = self.c.get(f'/register/verify/{email_verify.make_token(user)}/')

        self.assertEqual(r.status_code, 302)
        self.assertIn('confirm_error', r['Location'])
        self.assertIn('expired', r['Location'])
        self.assertFalse(User.objects.get(email='juan@gmail.com').email_verified)

    def test_a_forged_link_confirms_nothing(self):
        self._register()
        r = self.c.get('/register/verify/madeup.token.here/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('confirm_error', r['Location'])
        self.assertFalse(User.objects.get(email='juan@gmail.com').email_verified)

    def test_the_waiting_room_asks_for_confirmation_until_it_happens(self):
        self._register()
        r = self.c.get('/register/received/')
        self.assertTrue(r.context['confirm_email'])
        self.assertContains(r, 'Confirm your email address')
        self.assertContains(r, '/register/resend/')

    # ── Resending ───────────────────────────────────────────────────────────

    def test_the_link_can_be_sent_again(self):
        self._register()
        mail.outbox.clear()

        r = self.c.post('/register/resend/')
        self.assertRedirects(r, '/register/received/?resent=1',
                             fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/register/verify/', mail.outbox[0].body)

    def test_resend_only_ever_writes_to_this_browsers_own_registration(self):
        """Otherwise it is a way to make the site email anyone on demand."""
        self._register()
        mail.outbox.clear()

        stranger = Client()                 # no registration in its session
        r = stranger.post('/register/resend/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('confirm_error', r['Location'])
        self.assertEqual(len(mail.outbox), 0)

    def test_resending_after_confirming_just_says_it_is_done(self):
        self._register()
        self.c.get(self._link())
        mail.outbox.clear()

        r = self.c.post('/register/resend/')
        self.assertRedirects(r, '/register/received/?confirmed=1',
                             fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)


class DecisionEmailTest(TestCase):
    """What the applicant is told when the SDSO decides, and what the office sees."""

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.officer = User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='pw', role='vpsea')
        self.applicant = User.objects.create_user(
            username='juan@gmail.com', email='juan@gmail.com', password='pw',
            first_name='Juan', last_name='Cruz', role='student',
            verification_status='pending', email_verified=False)
        StudentProfile.objects.create(user=self.applicant, student_id='23-0001')

        self.c = Client()
        self.assertTrue(self.c.login(email='sdso@bipsu.edu.ph', password='pw'))

    def _decide(self, action, message=''):
        return self.c.post('/vpsea/accounts/', {
            'user_id': self.applicant.id, 'action': action, 'message': message})

    def test_approving_emails_the_applicant(self):
        self._decide('approve', 'Checked against the enrolment list.')

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['juan@gmail.com'])
        self.assertIn('Account verified', message.subject)
        self.assertIn('Checked against the enrolment list.', message.body)
        # An inbox supplies none of the context a portal does, so the message
        # has to say who it is from and what to do next.
        self.assertIn('Juan', message.body)
        self.assertIn('verified', message.body)
        self.assertIn('sign in', message.body.lower())

    def test_rejecting_emails_the_applicant_too(self):
        """They have no portal to read a notification in — the email is all there is."""
        self._decide('reject', 'That student ID is not on our enrolment list.')

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['juan@gmail.com'])
        self.assertIn('Account not verified', message.subject)
        self.assertIn('not on our enrolment list', message.body)
        # And what they can do about it, since nothing else will tell them.
        self.assertIn('contact the SDSO office', message.body)

    def test_approving_with_no_message_still_says_something_useful(self):
        self._decide('approve')
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('has been verified', body)
        self.assertIn('sign in', body.lower())

    def test_the_bell_keeps_the_offices_own_words_not_the_letter(self):
        """In the portal the surrounding context is already on the screen."""
        from api.models import Notification

        self._decide('approve', 'Checked against the enrolment list.')
        note = Notification.objects.get(student__user=self.applicant)
        self.assertEqual(note.title, 'Account verified')
        self.assertEqual(note.body, 'Checked against the enrolment list.')
        self.assertNotIn('Hi Juan', note.body)

    @override_settings(EMAIL_ENABLED=True)
    def test_the_office_is_told_the_email_went_out(self):
        r = self._decide('approve', 'Welcome.')
        self.assertIn('emailed=1', r['Location'])
        self.assertContains(self.c.get(r['Location']), 'They have been emailed')

    @override_settings(EMAIL_ENABLED=False)
    def test_delivery_is_not_claimed_where_nothing_is_actually_sent(self):
        """The console backend accepts everything and reports success.

        Saying 'they have been emailed' on the strength of that is the silent
        lie the standing warning exists to stop.
        """
        r = self._decide('approve', 'Welcome.')
        page = self.c.get(r['Location'])
        self.assertNotContains(page, 'They have been emailed')
        self.assertContains(page, 'Email is not configured on this deployment')

    @override_settings(EMAIL_ENABLED=True)
    def test_the_office_is_told_when_the_email_did_not_go_out(self):
        """A mail server that is down used to look exactly like one that worked."""
        with self.settings(EMAIL_BACKEND='api.test_email_verification.BrokenBackend'):
            r = self._decide('reject', 'Not on the list.')

        self.assertIn('emailed=0', r['Location'])
        self.assertContains(self.c.get(r['Location']),
                            'the email did not go out')
        # The decision itself is not lost because the announcement failed.
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.verification_status, 'rejected')

    # ── What the officer sees while deciding ────────────────────────────────

    def test_an_unconfirmed_address_is_flagged_on_the_queue(self):
        from django.utils import timezone
        self.applicant.email_confirmation_sent_at = timezone.now()
        self.applicant.save(update_fields=['email_confirmation_sent_at'])

        self.assertContains(self.c.get('/vpsea/accounts/'),
                            'Email address not confirmed')

    def test_a_confirmed_address_is_shown_as_confirmed(self):
        self.applicant.mark_email_verified()
        r = self.c.get('/vpsea/accounts/')
        self.assertContains(r, 'Email address confirmed by them')
        self.assertNotContains(r, 'Email address not confirmed')

    def test_an_unconfirmed_address_does_not_block_the_decision(self):
        """Mail is optional here; a gate would strand every applicant without it."""
        self.assertFalse(self.applicant.email_verified)
        self._decide('approve', 'Verified in person at the office.')

        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.verification_status, 'approved')
        self.assertTrue(self.applicant.can_sign_in)

    @override_settings(EMAIL_ENABLED=False)
    def test_the_office_is_warned_when_no_mail_server_is_configured(self):
        self.assertContains(self.c.get('/vpsea/accounts/'),
                            'Email is not configured on this deployment')

    @override_settings(EMAIL_ENABLED=True)
    def test_that_warning_is_absent_once_mail_is_configured(self):
        self.assertNotContains(self.c.get('/vpsea/accounts/'),
                               'Email is not configured on this deployment')


class OfficeAccountsAreExemptTest(TestCase):
    """An account the office creates is not asked to prove an address to itself."""

    def test_a_created_account_starts_confirmed(self):
        user = User.objects.create_user(
            username='staff@bipsu.edu.ph', email='staff@bipsu.edu.ph',
            password='pw', role='vpsea')
        self.assertTrue(user.email_verified)

    def test_only_the_public_form_withholds_that_trust(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        Client().post('/register/', {
            'account_type': 'student', 'first_name': 'Juan', 'last_name': 'Cruz',
            'email': 'juan@gmail.com', 'password': 'pw12345',
            'confirm_password': 'pw12345', 'student_id': '23-0001',
            'course': 'BSCS', 'year_level': '1',
        })
        self.assertFalse(User.objects.get(email='juan@gmail.com').email_verified)
