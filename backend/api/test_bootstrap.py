"""Preparing an empty deployment.

build.sh runs `bootstrap` on every deploy, so the interesting cases are not the
first run but the second and third: it must not duplicate anything, and above
all it must not reset a password an office has since changed. Getting that
wrong would silently restore a known password on every deploy.
"""

from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from .models import Scholarship, SystemSettings

User = get_user_model()

ENV = {
    'SDSO_EMAIL': 'sdso@bipsu.edu.ph',
    'SDSO_PASSWORD': 'a-password-only-used-in-tests',
    'UNIFAST_EMAIL': 'unifast@bipsu.edu.ph',
    'UNIFAST_PASSWORD': 'another-test-only-password',
}


def run(**overrides):
    env = dict(ENV)
    env.update(overrides)
    out = StringIO()
    with mock.patch.dict('os.environ', env, clear=False):
        call_command('bootstrap', stdout=out)
    return out.getvalue()


class BootstrapTest(TestCase):

    def test_it_creates_both_offices_and_the_catalogue(self):
        run()
        sdso = User.objects.get(email='sdso@bipsu.edu.ph')
        unifast = User.objects.get(email='unifast@bipsu.edu.ph')

        self.assertEqual(sdso.role, 'vpsea')
        self.assertEqual(unifast.role, 'unifast')
        self.assertEqual(Scholarship.objects.count(), 10)
        self.assertTrue(SystemSettings.objects.filter(pk=1).exists())

    def test_the_sdso_is_a_superuser_and_the_unifast_office_is_not(self):
        run()
        self.assertTrue(User.objects.get(email='sdso@bipsu.edu.ph').is_superuser)
        self.assertFalse(User.objects.get(email='unifast@bipsu.edu.ph').is_superuser)

    def test_both_offices_can_actually_sign_in(self):
        """Created accounts must not land in the verification queue.

        Registration sets that; an account the deployment creates is verified
        by the act of creating it, and an office stuck 'pending' on a fresh
        database would have nobody able to release it.
        """
        run()
        for email in ('sdso@bipsu.edu.ph', 'unifast@bipsu.edu.ph'):
            self.assertTrue(User.objects.get(email=email).can_sign_in, email)
            self.assertTrue(self.client.login(
                email=email, password=ENV['SDSO_PASSWORD']
                if email.startswith('sdso') else ENV['UNIFAST_PASSWORD']))
            self.client.logout()

    # ── running it again, which every deploy does ────────────────────────────

    def test_running_it_twice_creates_nothing_the_second_time(self):
        run()
        run()
        self.assertEqual(User.objects.filter(email='sdso@bipsu.edu.ph').count(), 1)
        self.assertEqual(Scholarship.objects.count(), 10)
        self.assertEqual(SystemSettings.objects.filter(pk=1).count(), 1)

    def test_a_password_changed_since_the_first_deploy_survives_the_next_one(self):
        """The failure this guards against is silent and serious.

        If bootstrap reset the password each run, an office that had rotated a
        leaked password would find the old one working again after any deploy.
        """
        run()
        user = User.objects.get(email='sdso@bipsu.edu.ph')
        user.set_password('the-office-changed-it-to-this')
        user.save()

        run()

        user.refresh_from_db()
        self.assertTrue(user.check_password('the-office-changed-it-to-this'))
        self.assertFalse(user.check_password(ENV['SDSO_PASSWORD']))

    # ── refusing to invent credentials ───────────────────────────────────────

    def test_an_office_with_no_password_set_is_skipped_not_given_a_default(self):
        output = run(SDSO_PASSWORD='')
        self.assertFalse(User.objects.filter(email='sdso@bipsu.edu.ph').exists())
        self.assertIn('SKIPPED', output)
        self.assertIn('SDSO_PASSWORD', output)
        # The other office is unaffected by its neighbour being skipped.
        self.assertTrue(User.objects.filter(email='unifast@bipsu.edu.ph').exists())

    def test_the_email_can_be_overridden_from_the_environment(self):
        run(SDSO_EMAIL='scholarships@bipsu.edu.ph')
        self.assertTrue(User.objects.filter(email='scholarships@bipsu.edu.ph').exists())

    def test_an_existing_account_is_matched_case_insensitively(self):
        """Otherwise a differently-cased address would create a second office."""
        run()
        run(SDSO_EMAIL='SDSO@BiPSU.edu.ph')
        self.assertEqual(User.objects.filter(email__iexact='sdso@bipsu.edu.ph').count(), 1)


class CatalogueTest(TestCase):

    # Which office funds a programme decides who reviews it and which report a
    # scholar lands in. `group` defaults to 'internal', so a row that omits it
    # is silently filed as BiPSU-funded — that is what shipped the first time.
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
        """landing.html renders `eligibility_list`; empty leaves a blank card."""
        run()
        for s in Scholarship.objects.all():
            self.assertTrue(s.eligibility_list, f'{s.name} has no eligibility_list')

    def test_recommended_programmes_carry_the_prose_eligibility_too(self):
        """student/recommendations.html renders the plain `eligibility` text.

        Only that page does, and it lists recommendation-category programmes,
        so the requirement stops there — TES is applied for directly and has
        no prose eligibility in the working catalogue.
        """
        run()
        for s in Scholarship.objects.filter(category='recommendation'):
            self.assertTrue(s.eligibility, f'{s.name} has no eligibility text')

    def test_a_row_already_wrong_in_the_database_is_corrected(self):
        """The deployed database had programmes under the wrong office.

        Creating only what is missing would leave them wrong forever, since
        there is no shell to fix them from.
        """
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
        """Matching on type, not name, is what keeps a rename from adding a row."""
        run()
        renamed = Scholarship.objects.get(type='TDP')
        renamed.name = 'Something An Office Typed'
        renamed.save()

        run()

        self.assertEqual(Scholarship.objects.filter(type='TDP').count(), 1)
        self.assertEqual(Scholarship.objects.count(), 10)

    def test_the_types_the_approval_routes_look_up_all_exist(self):
        """Approving an award fetches its Scholarship by type.

        A missing type does not raise — it just produces no Application, so the
        scholar never reaches the masterlist. That is why these are asserted by
        name rather than counted.
        """
        run()
        for kind in ('Academic', 'TES', 'TDP', 'Staff', 'Affirmative'):
            self.assertTrue(
                Scholarship.objects.filter(type=kind).exists(),
                f'no Scholarship row of type {kind!r}')
