"""The office can say whose seal a programme it adds should wear.

`Scholarship.logo_url` resolved the seal from the programme type alone, which
covers every programme in the catalogue and nothing else. A programme added
through /vpsea/scholarships/add/ has a type the funding map has never heard of,
so it fell back to BiPSU's seal whoever funds it — the exact fault the mapping
exists to prevent, reintroduced through the one route that can create a
programme the map cannot know about.

The stored value is a bare filename rendered straight into an `<img src>`, so
the view validates it against the files that actually exist rather than trusting
the post. Anything else — a path, a URL, a deleted seal — is discarded and the
programme falls back to its type's default.

It is a picker over the seals committed to `media/logos/` rather than an upload.
That folder is served off the filesystem (`api.media_views` reads it through
`FileSystemStorage`, deliberately not the uploads bucket), and Render's disk does
not survive a deploy — an uploaded seal would be gone at the next one.
"""
from django.test import Client, TestCase

from api.constants import available_logos
from api.models import Scholarship, SystemSettings, User


class ScholarshipLogoPickerTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='pw', first_name='S', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='sdso@bipsu.edu.ph', password='pw'))

    def _add(self, **extra):
        return self.c.post('/vpsea/scholarships/add/', dict({
            'name': 'Provincial Board Scholarship', 'type': 'ProvBoard',
            'group': 'external', 'description': 'x',
        }, **extra))

    # ── The gap this closes ─────────────────────────────────────────────────

    def test_a_programme_the_office_adds_can_carry_its_funders_seal(self):
        self._add(logo='CHED.png')
        s = Scholarship.objects.get(type='ProvBoard')
        self.assertEqual(s.logo, 'CHED.png')
        self.assertEqual(s.logo_url, '/media/logos/CHED.png')

    def test_without_a_choice_it_still_falls_back_to_the_type_default(self):
        """Unchanged behaviour for every programme in the catalogue."""
        self._add()
        s = Scholarship.objects.get(type='ProvBoard')
        self.assertEqual(s.logo, '')
        self.assertEqual(s.logo_url, '/media/logos/BiPSU.png')

    def test_a_catalogue_programme_still_resolves_from_its_type(self):
        """The chosen seal is an override, not a replacement for the map."""
        s = Scholarship.objects.create(
            name='DOST', type='DOST', category='recommendation',
            description='x', eligibility='x', requirements=[])
        self.assertEqual(s.logo_url, '/media/logos/DOST.png')

    def test_a_choice_beats_the_type_default(self):
        s = Scholarship.objects.create(
            name='DOST', type='DOST', category='recommendation',
            description='x', eligibility='x', requirements=[], logo='UniFAST.png')
        self.assertEqual(s.logo_url, '/media/logos/UniFAST.png')

    # ── What may be stored ──────────────────────────────────────────────────

    def test_a_path_is_refused_rather_than_stored(self):
        """The value is rendered into a URL, so this is the one that matters."""
        self._add(logo='../../../etc/passwd')
        self.assertEqual(Scholarship.objects.get(type='ProvBoard').logo, '')

    def test_a_seal_that_does_not_exist_is_refused(self):
        self._add(logo='NotARealAgency.png')
        self.assertEqual(Scholarship.objects.get(type='ProvBoard').logo, '')

    def test_every_offered_seal_is_a_bare_filename(self):
        for name in available_logos():
            with self.subTest(logo=name):
                self.assertNotIn('/', name)
                self.assertNotIn('\\', name)

    def test_the_seals_on_file_are_the_ones_offered(self):
        self.assertIn('BiPSU.png', available_logos())
        self.assertIn('CHED.png', available_logos())
        self.assertIn('UniFAST.png', available_logos())

    # ── Editing ─────────────────────────────────────────────────────────────

    def test_the_seal_can_be_changed_later(self):
        self._add(logo='CHED.png')
        s = Scholarship.objects.get(type='ProvBoard')
        self.c.post(f'/vpsea/scholarships/{s.pk}/edit/', {
            'name': s.name, 'type': s.type, 'group': 'external',
            'description': 'x', 'logo': 'DOST.png',
        })
        s.refresh_from_db()
        self.assertEqual(s.logo_url, '/media/logos/DOST.png')

    def test_it_can_be_cleared_back_to_the_type_default(self):
        self._add(logo='CHED.png')
        s = Scholarship.objects.get(type='ProvBoard')
        self.c.post(f'/vpsea/scholarships/{s.pk}/edit/', {
            'name': s.name, 'type': s.type, 'group': 'external',
            'description': 'x', 'logo': '',
        })
        s.refresh_from_db()
        self.assertEqual(s.logo_url, '/media/logos/BiPSU.png')

    # ── The form ────────────────────────────────────────────────────────────

    def test_the_add_form_offers_the_seals_on_file(self):
        html = self.c.get('/vpsea/scholarships/add/').content.decode()
        self.assertIn('data-logo-picker', html)
        self.assertIn('CHED.png', html)
        self.assertIn('Default for this programme type', html)

    def test_the_edit_form_preselects_the_chosen_seal(self):
        self._add(logo='CHED.png')
        s = Scholarship.objects.get(type='ProvBoard')
        html = self.c.get(f'/vpsea/scholarships/{s.pk}/edit/').content.decode()
        self.assertIn('value="CHED.png" selected', html)

    def test_the_landing_page_shows_the_chosen_seal(self):
        """End to end: the reason the field exists at all."""
        self._add(logo='CHED.png')
        html = Client().get('/').content.decode()
        self.assertIn('Provincial Board Scholarship', html)
        self.assertIn('/media/logos/CHED.png', html)
