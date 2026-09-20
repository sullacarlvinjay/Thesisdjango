from django.core import mail
from django.test import Client, TestCase

from api.models import ActivityLog, User


def an_officer(email='vp@bipsu.edu.ph', **extra):
    """An office account that may also open and close the others."""
    extra.setdefault('is_superuser', True)
    extra.setdefault('is_staff', True)
    return User.objects.create_user(
        username=email, email=email, password='office-pw-1',
        role='vpsea', first_name='Rosa', last_name='Bello', **extra)


def an_employee(email='mila@bipsu.edu.ph'):
    """An office account opened from the panel: same portal, no say over it."""
    return User.objects.create_user(
        username=email, email=email, password='office-pw-1',
        role='vpsea', first_name='Mila', last_name='Cruz')


class OpeningASecondOfficeAccountTest(TestCase):
    """The office is a role, not a person.

    A university office outlives whoever staffs it and rarely staffs it with
    one person. What these tests ask is whether a second officer can be given
    their own login without anyone having to share a password.
    """

    def setUp(self):
        self.vp = an_officer()
        self.c = Client()
        self.c.force_login(self.vp)

    def post(self, **data):
        return self.c.post('/vpsea/accounts/', data)

    def test_the_new_account_reaches_the_same_pages_as_the_one_that_made_it(self):
        self.post(office='create', first_name='Mila', last_name='Cruz',
                  email='mila@bipsu.edu.ph', password='another-pw-1')

        made = User.objects.get(email='mila@bipsu.edu.ph')
        theirs = Client()
        self.assertTrue(theirs.login(username='mila@bipsu.edu.ph',
                                     password='another-pw-1'))
        for page in ('/vpsea/', '/vpsea/accounts/', '/vpsea/renewals/',
                     '/vpsea/affirmative/', '/vpsea/archives/'):
            self.assertEqual(theirs.get(page).status_code, 200,
                             f'{page} refused the second office account')
        self.assertEqual(made.role, self.vp.role)

    def test_the_password_is_never_emailed_or_echoed_back(self):
        r = self.post(office='create', first_name='Mila',
                      email='mila@bipsu.edu.ph', password='another-pw-1')
        self.assertNotIn('another-pw-1', r.url)
        self.assertEqual(mail.outbox, [])

    def test_a_short_password_opens_no_account(self):
        self.post(office='create', first_name='Mila',
                  email='mila@bipsu.edu.ph', password='short')
        self.assertFalse(User.objects.filter(email='mila@bipsu.edu.ph').exists())

    def test_an_address_that_already_signs_in_is_refused(self):
        User.objects.create_user(username='taken@bipsu.edu.ph',
                                 email='taken@bipsu.edu.ph', password='pw',
                                 role='student')
        self.post(office='create', first_name='Mila',
                  email='taken@bipsu.edu.ph', password='another-pw-1')
        self.assertEqual(
            User.objects.filter(email='taken@bipsu.edu.ph').count(), 1)
        self.assertEqual(
            User.objects.get(email='taken@bipsu.edu.ph').role, 'student',
            'an existing account was overwritten into the office')

    def test_opening_one_is_itself_audited(self):
        self.post(office='create', first_name='Mila',
                  email='mila@bipsu.edu.ph', password='another-pw-1')
        entry = ActivityLog.objects.filter(verb='create').latest('created_at')
        self.assertEqual(entry.user, self.vp)
        self.assertIn('mila@bipsu.edu.ph', entry.action)

    def test_only_the_office_may_open_one(self):
        student = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            role='student')
        theirs = Client()
        theirs.force_login(student)
        theirs.post('/vpsea/accounts/', {
            'office': 'create', 'first_name': 'Mila',
            'email': 'mila@bipsu.edu.ph', 'password': 'another-pw-1'})
        self.assertFalse(User.objects.filter(email='mila@bipsu.edu.ph').exists())


class ClosingAnOfficeAccountTest(TestCase):
    """Closed rather than deleted, and never the last way in."""

    def setUp(self):
        self.vp = an_officer()
        self.other = an_officer('mila@bipsu.edu.ph')
        self.c = Client()
        self.c.force_login(self.vp)

    def close(self, account, active='0'):
        return self.c.post('/vpsea/accounts/', {
            'office': 'access', 'account_id': account.pk, 'active': active})

    def test_a_closed_account_cannot_sign_in_but_is_still_on_file(self):
        self.close(self.other)

        self.other.refresh_from_db()
        self.assertFalse(self.other.is_active)
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertFalse(Client().login(username='mila@bipsu.edu.ph',
                                        password='office-pw-1'))

    def test_a_closed_account_can_be_reopened(self):
        self.other.is_active = False
        self.other.save(update_fields=['is_active'])
        self.close(self.other, active='1')
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_active)

    def test_the_last_way_into_the_office_cannot_be_closed(self):
        self.other.delete()
        self.close(self.vp)
        self.vp.refresh_from_db()
        self.assertTrue(self.vp.is_active)

    def test_an_office_account_cannot_close_itself(self):
        self.close(self.vp)
        self.vp.refresh_from_db()
        self.assertTrue(self.vp.is_active)

    def test_a_student_account_is_not_reachable_through_this_door(self):
        student = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph', password='pw',
            role='student')
        self.close(student)
        student.refresh_from_db()
        self.assertTrue(student.is_active)


class AnOpenedAccountCannotTurnOnTheOneThatOpenedItTest(TestCase):
    """The employee reaches the same work, not the same authority.

    Two accounts that can each close the other is not a second officer, it is
    a race. The employee keeps every scholarship page; what they do not get is
    the power to lock out the account that opened theirs.
    """

    def setUp(self):
        self.rosa = an_officer()
        self.mila = an_employee()
        self.c = Client()
        self.c.force_login(self.mila)

    def test_they_cannot_close_the_account_that_opened_theirs(self):
        self.c.post('/vpsea/accounts/', {
            'office': 'access', 'account_id': self.rosa.pk, 'active': '0'})

        self.rosa.refresh_from_db()
        self.assertTrue(self.rosa.is_active)
        self.assertTrue(Client().login(username='vp@bipsu.edu.ph',
                                       password='office-pw-1'))

    def test_they_cannot_reset_that_account_s_password(self):
        self.c.post('/vpsea/accounts/', {
            'office': 'reset', 'account_id': self.rosa.pk,
            'password': 'taken-over-1'})

        self.rosa.refresh_from_db()
        self.assertTrue(self.rosa.check_password('office-pw-1'))

    def test_they_cannot_open_a_further_account(self):
        self.c.post('/vpsea/accounts/', {
            'office': 'create', 'first_name': 'Third',
            'email': 'third@bipsu.edu.ph', 'password': 'another-pw-1'})

        self.assertFalse(User.objects.filter(email='third@bipsu.edu.ph').exists())

    def test_they_still_reach_every_page_of_the_portal(self):
        for page in ('/vpsea/', '/vpsea/accounts/', '/vpsea/renewals/',
                     '/vpsea/affirmative/', '/vpsea/archives/',
                     '/vpsea/reports/', '/vpsea/scholarships/'):
            self.assertEqual(self.c.get(page).status_code, 200,
                             f'{page} refused an opened office account')

    def test_they_can_see_who_else_signs_in_without_being_offered_the_controls(self):
        page = self.c.get('/vpsea/accounts/').content.decode()

        self.assertIn('vp@bipsu.edu.ph', page)
        self.assertNotIn('Open the account', page)
        self.assertNotIn('office-accounts__acts', page)

    def test_the_account_that_opened_theirs_keeps_the_controls(self):
        hers = Client()
        hers.force_login(self.rosa)
        page = hers.get('/vpsea/accounts/').content.decode()

        self.assertIn('Open the account', page)
        self.assertIn('office-accounts__acts', page)

    def test_the_one_that_opened_it_can_still_close_it(self):
        hers = Client()
        hers.force_login(self.rosa)
        hers.post('/vpsea/accounts/', {
            'office': 'access', 'account_id': self.mila.pk, 'active': '0'})

        self.mila.refresh_from_db()
        self.assertFalse(self.mila.is_active)


class ResettingAnOfficePasswordTest(TestCase):

    def setUp(self):
        self.vp = an_officer()
        self.other = an_officer('mila@bipsu.edu.ph')
        self.c = Client()
        self.c.force_login(self.vp)

    def reset(self, account, password):
        return self.c.post('/vpsea/accounts/', {
            'office': 'reset', 'account_id': account.pk, 'password': password})

    def test_the_new_password_is_the_one_that_signs_them_in(self):
        self.reset(self.other, 'replaced-pw-1')

        theirs = Client()
        self.assertFalse(theirs.login(username='mila@bipsu.edu.ph',
                                      password='office-pw-1'))
        self.assertTrue(theirs.login(username='mila@bipsu.edu.ph',
                                     password='replaced-pw-1'))

    def test_your_own_password_is_not_changed_from_here(self):
        self.reset(self.vp, 'replaced-pw-1')
        self.vp.refresh_from_db()
        self.assertTrue(self.vp.check_password('office-pw-1'))

    def test_a_short_password_leaves_the_old_one_working(self):
        self.reset(self.other, 'short')
        self.other.refresh_from_db()
        self.assertTrue(self.other.check_password('office-pw-1'))
