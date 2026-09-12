"""The archive's programme picker, and CHED as two tabs rather than one.

Two changes, and they lean on each other.

CHED is the one programme the office reports in two blocks, and it used to show
both stacked inside a single tab. It is now a tab each. The tier rides as a
query parameter rather than as a scholarship type of its own, because ``type``
is the key the add form, the column set, the upload, the import history and the
download all look a programme up by — a 'CHED-Full' type would have to be
special-cased in every one of them, and the template conditions that read
``active_type in 'TDP DOST CHED Affirmative'`` would quietly stop matching.

The tabs themselves were a flat row of buttons, one per programme, laid out
``flex flex-wrap``. That is fine at nine and wraps onto a second and third line
by thirteen, pushing the table further down the card with every programme added
to the catalogue — and splitting CHED would have added one more. They are a
grouped menu now, so a new programme costs a row in a list instead.
"""
import html as html_lib
import re

from django.test import Client, TestCase

from api.models import (
    Application, ImportedScholar, Scholarship, StudentProfile, SystemSettings,
    User,
)


def tab_hrefs(html):
    """Every programme the picker offers, as the hrefs it offers them at.

    Unescaped, because the template writes a real `&amp;` into the attribute and
    what is checked here is where the link goes, not how it is spelt.
    """
    menu = re.search(r'id="archiveTabMenu".*?\n\s*</div>', html, re.S)
    found = re.findall(r'href="([^"]+)"', menu.group(0)) if menu else []
    return [html_lib.unescape(href) for href in found]


class ArchiveTabFixtures:
    """Two CHED scholars, one of each tier, plus an untiered imported row."""

    term = '26-1'

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': self.term,
                            'active_semester': '1st Semester'})
        self.ched = Scholarship.objects.create(
            name='CHED Merit', type='CHED', category='recommendation',
            group='external', description='x', eligibility='x', requirements=[])
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            group='internal', description='x', eligibility='x', requirements=[])

        self.full = self.scholar('Reyes', '2022-00001', 'Full Merit / Full Scholar')
        self.half = self.scholar('Santos', '2022-00002', 'Half Merit / Partial Scholar')
        self.imported = ImportedScholar.objects.create(
            scholarship_type='CHED', term_label=self.term, last_name='Cruz',
            first_name='Juan', gender='M', course='BSIT', year_level=2)

        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def scholar(self, last, student_id, scholar_type):
        user = User.objects.create_user(
            username=f'{student_id}@bipsu.edu.ph', password='pw',
            email=f'{student_id}@bipsu.edu.ph', first_name='A', last_name=last,
            role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id=student_id, course='BSCS', year_level=3,
            gender='Female', municipality='Naval')
        return Application.objects.create(
            student=profile, scholarship=self.ched, status='Approved',
            term_label=self.term, form_data={'scholar_type': scholar_type})

    def page(self, **query):
        response = self.c.get('/vpsea/archives/', query)
        self.assertEqual(response.status_code, 200)
        return response


class ChedIsTwoTabsTest(ArchiveTabFixtures, TestCase):

    # ── what the picker offers ──────────────────────────────────────────────

    def test_the_picker_offers_a_tab_for_each_ched_tier(self):
        hrefs = tab_hrefs(self.page(type='Academic').content.decode())
        self.assertIn('/vpsea/archives/?type=CHED&tier=Full', hrefs)
        self.assertIn('/vpsea/archives/?type=CHED&tier=Half', hrefs)

    def test_no_untiered_ched_tab_is_left_behind(self):
        """Three CHED entries would be one tab too many, and the bare one would
        be the only tab whose table disagreed with its own heading."""
        hrefs = tab_hrefs(self.page(type='Academic').content.decode())
        self.assertNotIn('/vpsea/archives/?type=CHED', hrefs)

    def test_every_other_programme_keeps_exactly_one_tab(self):
        html = self.page(type='Academic').content.decode()
        hrefs = tab_hrefs(html)
        self.assertEqual(hrefs.count('/vpsea/archives/?type=Academic'), 1)

    # ── which scholars each tab lists ───────────────────────────────────────

    def test_the_full_tab_lists_only_full_scholars(self):
        html = self.page(type='CHED', tier='Full').content.decode()
        self.assertIn('Reyes', html)
        self.assertNotIn('Santos', html)

    def test_the_half_tab_lists_only_half_scholars(self):
        html = self.page(type='CHED', tier='Half').content.decode()
        self.assertIn('Santos', html)
        self.assertNotIn('Reyes', html)

    def test_an_untiered_imported_row_still_prints_under_full(self):
        """Every CHED row uploaded before the split has a blank tier. Reading a
        blank as Half would move them all to the other tab on deploy."""
        self.assertEqual(self.imported.award_tier, '')
        self.assertIn('Cruz', self.page(type='CHED', tier='Full').content.decode())

    def test_an_imported_row_stays_where_the_report_has_always_put_it(self):
        """An imported CHED row carries no tier, and the masterlist has always
        printed an unclassified scholar under Full. Splitting the tabs does not
        move anybody: the row is on Full, exactly as it was in the Full block."""
        self.assertIn('Cruz', self.page(type='CHED', tier='Full').content.decode())
        self.assertNotIn('Cruz', self.page(type='CHED', tier='Half').content.decode())

    def test_between_them_the_two_tabs_hold_every_ched_scholar(self):
        """The split is a division, not a filter. Nobody may fall out of both."""
        both = (self.page(type='CHED', tier='Full').content.decode()
                + self.page(type='CHED', tier='Half').content.decode())
        for name in ('Reyes', 'Santos', 'Cruz'):
            with self.subTest(name=name):
                self.assertIn(name, both)

    # ── the tab you land on ─────────────────────────────────────────────────

    def test_a_bare_ched_url_lands_on_the_full_tab(self):
        """An old bookmark, or one of the redirects written before the split.
        Without this it renders with no tab lit and the picker names a tier the
        table is not showing."""
        response = self.page(type='CHED')
        self.assertEqual(response.context['active_tier'], 'Full')
        self.assertIn('Reyes', response.content.decode())

    def test_a_tier_that_is_not_a_tier_falls_back_to_full(self):
        self.assertEqual(self.page(type='CHED', tier='Platinum')
                         .context['active_tier'], 'Full')

    def test_a_tier_on_a_programme_that_has_none_is_ignored(self):
        """Only CHED is reported in blocks. A tier on Academic must not make
        the picker claim to be somewhere it is not."""
        response = self.page(type='Academic', tier='Full')
        self.assertEqual(response.context['active_tier'], '')
        self.assertEqual(response.context['active_tab_label'], 'Academic')

    def test_the_heading_names_the_tier_not_just_the_programme(self):
        self.assertEqual(self.page(type='CHED', tier='Half')
                         .context['active_tab_label'], 'CHED Half Merit')

    def test_the_block_band_is_dropped_once_the_tab_names_it(self):
        """The table used to carry a 'Full Merit / Full Scholar' band above it
        because one tab held both. With a tab per tier that band only repeats
        what the picker above it already says."""
        groups = self.page(type='CHED', tier='Full').context['scholar_groups']
        self.assertEqual(len(groups), 1)
        self.assertIsNone(groups[0]['title'])

    # ── adding a scholar from a tab ─────────────────────────────────────────

    def test_a_scholar_added_on_the_full_tab_is_stored_as_full(self):
        """ched_tier() reads a missing tier as Half. Without the tab stamping
        the tier, the office would add someone on Full and watch them appear on
        the other tab."""
        response = self.c.post('/vpsea/archives/add/', {
            'scholarship_type': 'CHED', 'tier': 'Full',
            'first_name': 'Mia', 'last_name': 'Torres',
            'student_id': '2022-00003', 'course': 'BSCS', 'year_level': '1',
            'gender': 'Female', 'create_account': 'no',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('tier=Full', response['Location'])
        self.assertIn('Torres', self.page(type='CHED', tier='Full').content.decode())

    def test_a_scholar_added_on_the_half_tab_is_stored_as_half(self):
        """The Full case passes whether or not the tier is stored, because an
        untiered row prints under Full anyway. This is the one that proves the
        tab is recorded — and it is why ImportedScholar needed a tier column:
        without one the Half tab could be read from and never added to."""
        self.c.post('/vpsea/archives/add/', {
            'scholarship_type': 'CHED', 'tier': 'Half',
            'first_name': 'Mia', 'last_name': 'Torres',
            'student_id': '2022-00004', 'course': 'BSCS', 'year_level': '1',
            'gender': 'Female', 'create_account': 'no',
        })
        self.assertIn('Torres', self.page(type='CHED', tier='Half').content.decode())
        self.assertNotIn('Torres', self.page(type='CHED', tier='Full').content.decode())

    # ── the workbook under the button ───────────────────────────────────────

    def test_the_download_link_on_a_tiered_tab_carries_the_tier(self):
        """Or the button under a one-block table hands back both blocks."""
        html = self.page(type='CHED', tier='Half').content.decode()
        self.assertIn('/vpsea/archives/download/?type=CHED&amp;tier=Half', html)

    def test_a_tiered_download_is_the_one_block(self):
        from io import BytesIO

        from openpyxl import load_workbook

        response = self.c.get('/vpsea/archives/download/',
                              {'type': 'CHED', 'tier': 'Full'})
        self.assertEqual(response.status_code, 200)
        rows = [list(r) for r in
                load_workbook(BytesIO(response.content)).active.iter_rows(values_only=True)]
        values = {str(v) for row in rows for v in row if v is not None}
        self.assertIn('Reyes', values)
        self.assertNotIn('Santos', values)
        self.assertNotIn('Half Merit / Partial Scholar', values)


class ThePickerScalesTest(ArchiveTabFixtures, TestCase):
    """The row of buttons is gone, and nothing fell out of the list with it."""

    def test_the_tab_strip_no_longer_wraps(self):
        """`flex flex-wrap gap-2` around one button per programme is what put a
        second and third line above the table as the catalogue grew.

        The toolbar row *outside* the picker still wraps, and should: that is
        the picker and the Upload / New Semester buttons folding under each
        other on a narrow screen, which is two items, not thirteen.
        """
        html = self.page(type='Academic').content.decode()
        picker = html.split('<div class="tab-picker">')[1].split('<div class="flex gap-2">')[0]
        self.assertNotIn('flex-wrap', picker)
        self.assertIn('tab-picker__menu', picker)

    def test_every_archive_type_is_still_reachable(self):
        """A menu that quietly dropped a programme would be worse than a row
        that wrapped."""
        response = self.page(type='Academic')
        hrefs = ' '.join(tab_hrefs(response.content.decode()))
        for stype in response.context['archive_types']:
            with self.subTest(type=stype):
                if stype == 'CHED':
                    self.assertIn('type=CHED&tier=', hrefs)
                else:
                    self.assertIn(f'type={stype.replace(" ", "%20")}', hrefs)

    def test_a_newly_catalogued_programme_files_itself_under_its_funder(self):
        Scholarship.objects.create(
            name='Governor Award', type="Governor's Award", category='application',
            group='external', description='x', eligibility='x', requirements=[])
        groups = self.page(type='Academic').context['archive_tabs']
        external = next(g for g in groups if g['label'] == 'External')
        self.assertIn("Governor's Award", [t['label'] for t in external['tabs']])

    def test_the_groups_are_the_catalogues_own(self):
        groups = {g['label'] for g in self.page(type='Academic').context['archive_tabs']}
        self.assertIn('Internal', groups)
        self.assertIn('External', groups)

    def test_the_unawarded_tab_is_not_filed_as_a_programme(self):
        """It lists students who hold no award. It has no funder, so it goes
        under Other rather than being dropped or called internal."""
        groups = self.page(type='Academic').context['archive_tabs']
        other = next(g for g in groups if g['label'] == 'Other')
        self.assertIn('No Scholarship', [t['label'] for t in other['tabs']])

    def test_exactly_one_tab_is_marked_current(self):
        for query in ({'type': 'Academic'}, {'type': 'CHED', 'tier': 'Half'}):
            with self.subTest(**query):
                groups = self.page(**query).context['archive_tabs']
                lit = [t for g in groups for t in g['tabs'] if t['active']]
                self.assertEqual(len(lit), 1)
