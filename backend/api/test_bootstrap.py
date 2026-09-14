from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from .catalogue import SCHOLARSHIPS
from .models import Scholarship, SystemSettings

User = get_user_model()

ENV = {
    'SDSO_EMAIL': 'sdso@bipsu.edu.ph',
    'SDSO_PASSWORD': 'a-password-only-used-in-tests',
}


def run(**overrides):
    env = dict(ENV)
    env.update(overrides)
    out = StringIO()
    with mock.patch.dict('os.environ', env, clear=False):
        call_command('bootstrap', stdout=out)
    return out.getvalue()


class BootstrapTest(TestCase):

    def test_it_creates_the_office_and_the_catalogue(self):
        run()
        sdso = User.objects.get(email='sdso@bipsu.edu.ph')

        self.assertEqual(sdso.role, 'vpsea')
        self.assertTrue(sdso.is_superuser)
        self.assertEqual(Scholarship.objects.count(), len(SCHOLARSHIPS))
        self.assertTrue(SystemSettings.objects.filter(pk=1).exists())

    def test_the_office_can_actually_sign_in(self):
        run()
        self.assertTrue(User.objects.get(email='sdso@bipsu.edu.ph').can_sign_in)
        self.assertTrue(self.client.login(
            email='sdso@bipsu.edu.ph', password=ENV['SDSO_PASSWORD']))
        self.client.logout()

    def test_running_it_twice_creates_nothing_the_second_time(self):
        run()
        run()
        self.assertEqual(User.objects.filter(email='sdso@bipsu.edu.ph').count(), 1)
        self.assertEqual(Scholarship.objects.count(), len(SCHOLARSHIPS))
        self.assertEqual(SystemSettings.objects.filter(pk=1).count(), 1)

    def test_a_password_changed_since_the_first_deploy_survives_the_next_one(self):
        run()
        user = User.objects.get(email='sdso@bipsu.edu.ph')
        user.set_password('the-office-changed-it-to-this')
        user.save()

        run()

        user.refresh_from_db()
        self.assertTrue(user.check_password('the-office-changed-it-to-this'))
        self.assertFalse(user.check_password(ENV['SDSO_PASSWORD']))

    def test_an_office_with_no_password_set_is_skipped_not_given_a_default(self):
        output = run(SDSO_PASSWORD='')
        self.assertFalse(User.objects.filter(email='sdso@bipsu.edu.ph').exists())
        self.assertIn('SKIPPED', output)
        self.assertIn('SDSO_PASSWORD', output)

    def test_the_email_can_be_overridden_from_the_environment(self):
        run(SDSO_EMAIL='scholarships@bipsu.edu.ph')
        self.assertTrue(User.objects.filter(email='scholarships@bipsu.edu.ph').exists())

    def test_an_existing_account_is_matched_case_insensitively(self):
        run()
        run(SDSO_EMAIL='SDSO@BiPSU.edu.ph')
        self.assertEqual(User.objects.filter(email__iexact='sdso@bipsu.edu.ph').count(), 1)


class CatalogueTest(TestCase):
    EXTERNAL = {'TDP', 'DOST', 'CHED', 'CoScho', 'GSIS', 'TES'}
    INTERNAL = {'Academic', 'Sports', 'Affirmative', 'Staff'}

    def test_externally_funded_programmes_are_not_filed_as_internal(self):
        run()
        for kind in self.EXTERNAL:
            self.assertEqual(
                Scholarship.objects.get(type=kind).group, 'external',
                f'{kind} should be external')

    def test_bipsu_funded_programmes_stay_internal(self):
        run()
        for kind in self.INTERNAL:
            self.assertEqual(
                Scholarship.objects.get(type=kind).group, 'internal',
                f'{kind} should be internal')

    def test_every_programme_carries_the_eligibility_the_landing_page_lists(self):
        run()
        for s in Scholarship.objects.all():
            self.assertTrue(s.eligibility_list, f'{s.name} has no eligibility_list')

    def test_recommended_programmes_carry_the_prose_eligibility_too(self):
        run()
        for s in Scholarship.objects.filter(category='recommendation'):
            self.assertTrue(s.eligibility, f'{s.name} has no eligibility text')

    def test_a_row_already_wrong_in_the_database_is_corrected(self):
        run()
        wrong = Scholarship.objects.get(type='TDP')
        wrong.group = 'internal'
        wrong.name = 'TDP Scholarship'
        wrong.eligibility_list = []
        wrong.save()

        run()

        fixed = Scholarship.objects.get(type='TDP')
        self.assertEqual(fixed.group, 'external')
        self.assertEqual(fixed.name, 'Tulong Dunong Program Scholarship')
        self.assertTrue(fixed.eligibility_list)

    def test_correcting_a_row_does_not_duplicate_it(self):
        run()
        renamed = Scholarship.objects.get(type='TDP')
        renamed.name = 'Something An Office Typed'
        renamed.save()

        run()

        self.assertEqual(Scholarship.objects.filter(type='TDP').count(), 1)
        self.assertEqual(Scholarship.objects.count(), len(SCHOLARSHIPS))

    def test_the_types_the_approval_routes_look_up_all_exist(self):
        run()
        for kind in ('Academic', 'TES', 'TDP', 'Staff', 'Affirmative'):
            self.assertTrue(
                Scholarship.objects.filter(type=kind).exists(),
                f'no Scholarship row of type {kind!r}')
