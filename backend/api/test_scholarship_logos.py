"""Every programme on the landing page wears its own funder's seal.

The page showed the BiPSU seal on all three card sections and in every modal,
including the programmes BiPSU does not fund. A DOST scholarship advertised
under the university's own logo is not a cosmetic slip — it is a claim about who
pays for it, made on the first page a prospective student sees.

The mapping follows the university's own programme chart: DOST runs the S&T
undergraduate scholarships and JLSS, CHED runs CHED-Merit and CoScho, and TES
and TDP are UniFAST's however often the two are spoken of together.
"""
import os

from django.conf import settings
from django.test import Client, TestCase

from api.constants import SCHOLARSHIP_LOGOS
from api.models import Scholarship


class ScholarshipLogoTest(TestCase):

    def _scholarship(self, type_, group='external'):
        return Scholarship.objects.create(
            name=f'{type_} Scholarship', type=type_, category='application',
            group=group, description='x', eligibility='x', requirements=[])

    def test_each_programme_points_at_its_own_funders_seal(self):
        for type_, expected in (('DOST', 'DOST.png'),
                                ('CHED', 'CHED.png'),
                                ('CoScho', 'CHED.png'),
                                ('TES', 'UniFAST.png'),
                                ('TDP', 'UniFAST.png'),
                                ('Academic', 'BiPSU.png')):
            with self.subTest(type=type_):
                self.assertEqual(self._scholarship(type_).logo_url,
                                 f'/media/logos/{expected}')

    def test_a_programme_with_no_agency_logo_falls_back_to_bipsu(self):
        """What every card showed before this existed — GSIS today."""
        self.assertEqual(self._scholarship('GSIS').logo_url, '/media/logos/BiPSU.png')

    def test_every_mapped_logo_is_a_file_that_exists(self):
        """A typo here is a broken image on the public landing page."""
        for type_, filename in SCHOLARSHIP_LOGOS.items():
            with self.subTest(type=type_):
                self.assertTrue(
                    os.path.exists(os.path.join(settings.MEDIA_ROOT, 'logos', filename)),
                    f'{type_} points at media/logos/{filename}, which is not there')

    def test_the_landing_page_renders_the_agency_seals(self):
        self._scholarship('DOST')
        self._scholarship('TES')
        self._scholarship('Academic', group='internal')

        html = Client().get('/').content.decode()
        self.assertIn('/media/logos/DOST.png', html)
        self.assertIn('/media/logos/UniFAST.png', html)
        # BiPSU's own seal is still on the navbar and on the internal card.
        self.assertIn('/media/logos/BiPSU.png', html)

    def test_an_external_card_no_longer_carries_the_university_seal(self):
        """The bug itself: DOST advertised under BiPSU's logo."""
        self._scholarship('DOST')

        html = Client().get('/').content.decode()
        card = html.split('card-strip-external')[1].split('</div>')[0:6]
        self.assertNotIn('BiPSU.png', ''.join(card))
