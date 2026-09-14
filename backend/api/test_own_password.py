from django.test import Client, TestCase

from api.models import PartnerOffice, Scholarship, SystemSettings, User


class OwnPasswordTestMixin:
    url = None
    email = None

    def _post(self, **fields):
        data = {'first_name': 'Given', 'last_name': 'Family'}
        data.update(fields)
        return self.c.post(self.url, data)

    def _signs_in_with(self, password):
        checker = Client()
        return checker.login(email=self.email, password=password)

    def test_the_password_changes(self):
        self._post(current_password='oldpassword1',
                   new_password='fresh-Passphrase-9',
                   new_password_confirm='fresh-Passphrase-9')
        self.assertTrue(self._signs_in_with('fresh-Passphrase-9'))
        self.assertFalse(self._signs_in_with('oldpassword1'))

    def test_and_the_page_says_so(self):
        page = self._post(current_password='oldpassword1',
                          new_password='fresh-Passphrase-9',
                          new_password_confirm='fresh-Passphrase-9')
        self.assertContains(page, 'your password has been changed')

    def test_the_person_is_not_signed_out_of_the_tab_they_did_it_in(self):
        self._post(current_password='oldpassword1',
                   new_password='fresh-Passphrase-9',
                   new_password_confirm='fresh-Passphrase-9')
        self.assertEqual(self.c.get(self.url).status_code, 200)

    def test_the_wrong_current_password_changes_nothing(self):
        page = self._post(current_password='not-the-password',
                          new_password='fresh-Passphrase-9',
                          new_password_confirm='fresh-Passphrase-9')
        self.assertContains(page, 'current password is not right')
        self.assertTrue(self._signs_in_with('oldpassword1'))

    def test_a_mistyped_repeat_changes_nothing(self):
        page = self._post(current_password='oldpassword1',
                          new_password='fresh-Passphrase-9',
                          new_password_confirm='fresh-Passphrase-8')
        self.assertContains(page, 'do not match')
        self.assertTrue(self._signs_in_with('oldpassword1'))

    def test_a_password_django_would_reject_is_refused_with_its_reason(self):
        page = self._post(current_password='oldpassword1',
                          new_password='12345', new_password_confirm='12345')
        self.assertTrue(self._signs_in_with('oldpassword1'))
        self.assertContains(page, 'too short', msg_prefix=str(page.context['errors']))

    def test_a_refused_change_does_not_save_the_name_either(self):
        self._post(first_name='Renamed', current_password='wrong',
                   new_password='fresh-Passphrase-9',
                   new_password_confirm='fresh-Passphrase-9')
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.first_name, 'Renamed')

    def test_saving_the_name_alone_leaves_the_password_standing(self):
        page = self._post(first_name='Renamed')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Renamed')
        self.assertTrue(self._signs_in_with('oldpassword1'))
        self.assertNotContains(page, 'your password has been changed')

    def test_a_signed_out_visitor_is_sent_to_the_login_page(self):
        self.assertEqual(Client().get(self.url).status_code, 302)

    def test_a_student_may_not_open_it(self):
        User.objects.create_user(username='s@bipsu.edu.ph', email='s@bipsu.edu.ph',
                                 password='pw', role='student')
        other = Client()
        self.assertTrue(other.login(email='s@bipsu.edu.ph', password='pw'))
        self.assertEqual(other.get(self.url).status_code, 302)


class TheSDSOProfileTest(OwnPasswordTestMixin, TestCase):
    url = '/vpsea/profile/'
    email = 'sdso@bipsu.edu.ph'

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.user = User.objects.create_user(
            username=self.email, email=self.email, password='oldpassword1',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email=self.email, password='oldpassword1'))

    def test_the_nav_offers_it(self):
        self.assertContains(self.c.get('/vpsea/'), '/vpsea/profile/')

    def test_the_email_is_shown_but_not_editable(self):
        page = self.c.get(self.url)
        self.assertContains(page, self.email)
        self.assertNotContains(page, 'name="email"')

    def test_the_email_cannot_be_changed_by_posting_one(self):
        self._post(email='someone-else@bipsu.edu.ph')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, self.email)


class ThePartnerProfileTest(OwnPasswordTestMixin, TestCase):
    url = '/partner/profile/'
    email = 'dost@agency.gov.ph'

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.office = PartnerOffice.objects.create(name='DOST Region VIII')
        self.user = User.objects.create_user(
            username=self.email, email=self.email, password='oldpassword1',
            first_name='D', last_name='Liaison', role='partner',
            partner_office=self.office)
        self.c = Client()
        self.assertTrue(self.c.login(email=self.email, password='oldpassword1'))

    def test_the_nav_offers_it(self):
        self.assertContains(self.c.get('/partner/'), '/partner/profile/')

    def test_the_office_is_named_and_not_editable(self):
        page = self.c.get(self.url)
        self.assertContains(page, 'DOST Region VIII')
        self.assertNotContains(page, 'name="partner_office"')

    def test_the_programmes_shared_with_it_are_shown(self):
        scholarship = Scholarship.objects.create(
            name='DOST S&T Undergraduate', type='DOST', category='recommendation',
            group='external', description='x', eligibility='x', requirements=[])
        self.office.scholarships.add(scholarship)
        self.assertContains(self.c.get(self.url), 'DOST S&amp;T Undergraduate')

    def test_an_account_with_none_is_told_that_is_not_the_same_as_no_scholars(self):
        self.assertContains(self.c.get(self.url), 'not the same')

    def test_the_programmes_cannot_be_granted_from_this_page(self):
        scholarship = Scholarship.objects.create(
            name='CHED Merit', type='CHED', category='recommendation',
            group='external', description='x', eligibility='x', requirements=[])
        self._post(scholarships=scholarship.pk)
        self.assertEqual(list(self.office.scholarships.all()), [])

    def test_an_account_whose_office_was_suspended_cannot_open_it(self):
        self.office.is_active = False
        self.office.save()
        self.assertEqual(self.c.get(self.url).status_code, 302)
