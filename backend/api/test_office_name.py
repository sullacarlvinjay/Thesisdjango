"""The office an SDSO account signs in on behalf of.

It used to be a readonly input with the office's name typed into the template,
which meant the field could not be wrong and could not be right either. These
drive the profile form and then read the account back, because a field that
renders a value but posts nothing would pass any test that only read the page.
"""

from django.test import Client, TestCase

from api.models import SystemSettings, User

SDSO = 'Student Development and Services Office'


class TheOfficeFieldTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.officer = User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='office-pw-1', role='vpsea',
            first_name='Given', last_name='Family')
        self.c = Client()
        self.c.login(email='sdso@bipsu.edu.ph', password='office-pw-1')

    def save(self, **fields):
        data = {'first_name': 'Given', 'last_name': 'Family',
                'email': 'sdso@bipsu.edu.ph'}
        data.update(fields)
        return self.c.post('/vpsea/profile/', data)

    def stored(self):
        self.officer.refresh_from_db()
        return self.officer.office_name

    def test_an_account_starts_out_named_for_the_office_it_belongs_to(self):
        self.assertEqual(self.stored(), SDSO)

    def test_the_field_posts_its_value_instead_of_being_readonly(self):
        page = self.c.get('/vpsea/profile/')
        self.assertContains(page, 'name="office_name"')
        self.assertNotContains(page, f'value="{SDSO}" readonly')

    def test_a_new_office_name_is_saved(self):
        self.save(office_name='Office of Student Affairs')
        self.assertEqual(self.stored(), 'Office of Student Affairs')

    def test_the_saved_name_is_what_the_page_reads_back(self):
        self.save(office_name='Office of Student Affairs')
        page = self.c.get('/vpsea/profile/')
        self.assertContains(page, 'Office of Student Affairs')
        self.assertNotContains(page, SDSO)

    def test_it_is_trimmed_rather_than_stored_with_the_spacing_typed(self):
        self.save(office_name='  Office of Student Affairs  ')
        self.assertEqual(self.stored(), 'Office of Student Affairs')

    def test_a_blank_one_leaves_the_office_named_as_it_was(self):
        self.save(office_name='   ')
        self.assertEqual(self.stored(), SDSO)

    def test_a_name_too_long_for_the_column_is_refused(self):
        ceiling = User._meta.get_field('office_name').max_length
        page = self.save(office_name='x' * (ceiling + 1))
        self.assertEqual(self.stored(), SDSO)
        self.assertContains(page, 'Keep it under')

    def test_saving_the_rest_of_the_card_does_not_disturb_it(self):
        self.save(office_name='Office of Student Affairs')
        self.save(first_name='Other')
        self.officer.refresh_from_db()
        self.assertEqual(self.officer.first_name, 'Other')
        self.assertEqual(self.officer.office_name, 'Office of Student Affairs')

    def test_the_sidebar_names_the_office_this_account_gave_itself(self):
        self.save(office_name='Office of Student Affairs')
        page = self.c.get('/vpsea/')
        self.assertContains(page, 'title="Office of Student Affairs"')

    def test_one_office_account_renaming_does_not_rename_another(self):
        other = User.objects.create_user(
            username='clerk@bipsu.edu.ph', email='clerk@bipsu.edu.ph',
            password='office-pw-2', role='vpsea')
        self.save(office_name='Office of Student Affairs')
        other.refresh_from_db()
        self.assertEqual(other.office_name, SDSO)
