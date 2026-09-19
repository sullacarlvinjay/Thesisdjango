import json
import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import Client, SimpleTestCase, TestCase, override_settings

from api.models import Scholarship, SignupSource, SystemSettings, User

CSS = settings.BASE_DIR / 'static' / 'css' / 'srms.css'
JS = settings.BASE_DIR / 'static' / 'js'


def template_files():
    for root in settings.TEMPLATES[0]['DIRS']:
        yield from Path(root).rglob('*.html')


class SignedOutPagesCarryTheChromeTest(TestCase):

    def setUp(self):
        SystemSettings.objects.get_or_create(pk=1)
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            group='internal', description='x', eligibility='x', requirements=[])
        self.c = Client()

    def landing(self):
        return self.c.get('/').content.decode()

    def test_the_landing_page_offers_a_skip_link_to_the_content(self):
        html = self.landing()
        self.assertIn('class="skip-link"', html)
        self.assertIn('href="#mainContent"', html)
        self.assertIn('id="mainContent"', html)

    def test_it_carries_a_scroll_progress_bar_and_a_way_back_up(self):
        html = self.landing()
        self.assertIn('class="scroll-progress"', html)
        self.assertIn('class="to-top"', html)

    def test_it_carries_the_cookie_notice_and_a_floating_contact(self):
        html = self.landing()
        self.assertIn('class="cookie-banner"', html)
        self.assertIn('class="fab-contact"', html)

    def test_the_card_search_is_either_wired_up_or_fully_removed(self):
        html = self.landing()
        if 'data-search="[data-scholarship]"' in html:
            self.assertIn('id="catalogueEmpty"', html)
            self.assertIn('js/search', html)
        else:
            self.assertNotIn('id="catalogueEmpty"', html,
                             'the search input is gone but its empty-state and '
                             'section markers were left behind')

    def test_it_answers_the_questions_people_actually_ask(self):
        html = self.landing()
        self.assertIn('id="help"', html)
        self.assertIn('class="faq-list"', html)
        self.assertGreaterEqual(html.count('class="faq-item"'), 5,
                                'an FAQ with fewer than five entries is decoration')

    def test_it_says_when_the_programme_details_last_changed(self):
        html = self.landing()
        self.assertIn('Program details last updated', html)
        self.assertIn('<time datetime=', html)

    def test_the_sign_in_page_loads_the_password_toggle_script(self):
        html = self.c.get('/login/').content.decode()
        self.assertIn('js/chrome', html)

    def test_a_missing_page_still_renders_the_branded_shell(self):
        response = self.c.get('/no-such-page/')
        self.assertEqual(response.status_code, 404)
        html = response.content.decode()
        self.assertIn('BiPSU SRMS', html)
        self.assertIn('css/srms', html)


class ThePortalCarriesTheChromeTest(TestCase):

    def setUp(self):
        SystemSettings.objects.get_or_create(pk=1)
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def page(self):
        return self.c.get('/vpsea/').content.decode()

    def test_the_portal_offers_a_skip_link(self):
        html = self.page()
        self.assertIn('class="skip-link"', html)
        self.assertIn('id="mainContent"', html)

    def test_the_sidebar_can_be_searched(self):
        html = self.page()
        self.assertIn('id="navSearch"', html)
        self.assertIn('data-search=".sidebar-nav .sidebar-link"', html)

    def test_every_chrome_script_is_loaded(self):
        html = self.page()
        for name in ('loading', 'chrome', 'consent', 'search'):
            self.assertIn(f'js/{name}', html, f'{name}.js never reaches the page')

    def test_the_office_is_not_offered_a_button_to_contact_itself(self):
        self.assertNotIn('class="fab-contact"', self.page())


class LoadingStatesReachTheMarkupTest(TestCase):

    def setUp(self):
        SystemSettings.objects.get_or_create(pk=1)
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def test_the_analytics_filters_announce_themselves_as_auto_submitting(self):
        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn('data-auto-submit', html)
        self.assertNotIn('onchange="this.form.submit()"', html,
                         'the inline handler gave the script no way to show a spinner')

    def test_the_script_marks_both_buttons_and_dropdowns_busy(self):
        source = (JS / 'loading.js').read_text(encoding='utf-8')
        self.assertIn("addEventListener('submit'", source)
        self.assertIn("addEventListener('change'", source)
        self.assertIn('control-spinner', source)

    def test_a_busy_button_never_loses_its_name_from_the_post(self):
        source = (JS / 'loading.js').read_text(encoding='utf-8')
        self.assertNotIn('disabled = true', source,
                         'disabling a submit button drops its name and value '
                         'from the request Django then reads')


class CampaignAttributionTest(TestCase):

    def setUp(self):
        SystemSettings.objects.get_or_create(pk=1)
        self.c = Client()

    def test_a_campaign_is_kept_against_the_address(self):
        from api.test_registration_payload import a_student

        payload = json.dumps({
            'utm_source': 'facebook', 'utm_medium': 'post',
            'utm_campaign': 'academic-2026', 'landed_on': '/',
        })
        self.c.post('/register/', a_student(email='jose@bipsu.edu.ph',
                                            utm_payload=payload))
        row = SignupSource.objects.get(email='jose@bipsu.edu.ph')
        self.assertEqual(row.utm_source, 'facebook')
        self.assertEqual(row.utm_campaign, 'academic-2026')
        self.assertEqual(row.campaign_label, 'facebook / post / academic-2026')

    def test_a_row_carrying_no_campaign_reads_as_direct(self):
        self.assertEqual(
            SignupSource(email='ana@example.com').campaign_label, 'direct')

    def test_rubbish_in_the_hidden_field_is_ignored_not_crashed_on(self):
        from api.test_registration_payload import a_student

        response = self.c.post('/register/', a_student(
            email='ana@bipsu.edu.ph', utm_payload='{not json at all'))
        self.assertIn(response.status_code, (200, 302))

    def test_an_overlong_payload_is_dropped_rather_than_stored(self):
        from api.test_registration_payload import a_student

        self.c.post('/register/', a_student(
            email='ana@bipsu.edu.ph',
            utm_payload=json.dumps({'utm_source': 'x' * 4000})))
        self.assertFalse(
            SignupSource.objects.filter(utm_source__startswith='x').exists())

    def test_the_registration_form_is_stamped_too(self):
        html = self.c.get('/register/').content.decode()
        self.assertIn('data-utm', html,
                      'without this the script never fills utm_payload in')
        self.assertIn('js/consent', html,
                      'the form is marked but nothing is loaded to stamp it')

    def test_where_a_registrant_came_from_is_kept(self):
        from api.test_registration_payload import a_student

        payload = json.dumps({'utm_source': 'tiktok', 'utm_campaign': 'open-house'})
        response = self.c.post(
            '/register/', a_student(email='lito@bipsu.edu.ph', utm_payload=payload))
        self.assertIn(response.status_code, (200, 302))

        row = SignupSource.objects.get(email='lito@bipsu.edu.ph')
        self.assertEqual(row.kind, 'registration')
        self.assertEqual(row.utm_source, 'tiktok')
        self.assertEqual(row.utm_campaign, 'open-house')

    def test_a_registrant_who_arrived_cold_leaves_no_empty_row(self):
        from api.test_registration_payload import a_student

        self.c.post('/register/', a_student(email='cold@bipsu.edu.ph'))
        self.assertFalse(
            SignupSource.objects.filter(kind='registration').exists(),
            'a row with no campaign on it says nothing and just grows the table')

    def test_the_script_strips_the_campaign_out_of_the_visible_address(self):
        source = (JS / 'consent.js').read_text(encoding='utf-8')
        self.assertIn('replaceState', source)
        self.assertIn('params.delete', source)


class TheCatalogueIsCachedTest(TestCase):

    def setUp(self):
        SystemSettings.objects.get_or_create(pk=1)
        self.c = Client()

    @override_settings(CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'catalogue-test'}})
    def test_a_warm_page_costs_the_same_however_many_programmes_there_are(self):
        from django.core.cache import caches
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        def visits_with(count):
            caches['default'].clear()
            Scholarship.objects.all().delete()
            for n in range(count):
                Scholarship.objects.create(
                    name=f'Scholarship {n}', type=f'T{n}', category='application',
                    group='internal', description='x', eligibility='x',
                    requirements=[])
            self.c.get('/')
            with CaptureQueriesContext(connection) as captured:
                self.c.get('/')
            return len(captured)

        self.assertEqual(visits_with(1), visits_with(12),
                         'the catalogue is being re-read instead of cached')

    @override_settings(CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'catalogue-change-test'}})
    def test_editing_a_programme_shows_up_straight_away(self):
        from django.core.cache import caches
        caches['default'].clear()
        row = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            group='internal', description='x', eligibility='x', requirements=[])
        self.assertIn('Academic Scholarship', self.c.get('/').content.decode())
        row.name = 'Renamed Scholarship'
        row.save()
        html = self.c.get('/').content.decode()
        self.assertIn('Renamed Scholarship', html)
        self.assertNotIn('Academic Scholarship', html)

    @override_settings(CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'catalogue-delete-test'}})
    def test_retiring_a_programme_takes_it_off_the_page(self):
        from django.core.cache import caches
        caches['default'].clear()
        row = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            group='internal', description='x', eligibility='x', requirements=[])
        self.assertIn('Academic Scholarship', self.c.get('/').content.decode())
        row.is_active = False
        row.save()
        self.assertNotIn('Academic Scholarship', self.c.get('/').content.decode())


class AnalyticsRemembersItsWorkTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    @override_settings(CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'analytics-test'}})
    def test_the_page_says_when_the_figures_were_worked_out(self):
        from django.core.cache import caches
        caches['default'].clear()
        first = self.c.get('/vpsea/analytics/')
        self.assertFalse(first.context['analytics_cached'])
        self.assertIn('Figures worked out', first.content.decode())

        second = self.c.get('/vpsea/analytics/')
        self.assertTrue(second.context['analytics_cached'])
        self.assertEqual(first.context['analytics_generated'],
                         second.context['analytics_generated'])

    @override_settings(CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'analytics-refresh-test'}})
    def test_the_office_can_force_a_recalculation(self):
        from django.core.cache import caches
        caches['default'].clear()
        first = self.c.get('/vpsea/analytics/')
        again = self.c.get('/vpsea/analytics/', {'refresh': '1'})
        self.assertFalse(again.context['analytics_cached'])
        self.assertGreater(again.context['analytics_generated'],
                           first.context['analytics_generated'])

    @override_settings(CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'analytics-stale-test'}})
    def test_a_new_scholar_is_not_hidden_behind_yesterdays_figures(self):
        from django.core.cache import caches

        from api.models import Application, StudentProfile

        caches['default'].clear()
        scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        self.assertFalse(self.c.get('/vpsea/analytics/').context['show_program'])

        student = User.objects.create_user(
            username='s1@bipsu.edu.ph', email='s1@bipsu.edu.ph', password='pw',
            first_name='S', last_name='Lim', role='student')
        profile = StudentProfile.objects.create(
            user=student, student_id='2022-00001', course='BSCE', year_level=2, gwa=1.2)
        Application.objects.create(student=profile, scholarship=scholarship,
                                   status='Approved')

        self.assertTrue(self.c.get('/vpsea/analytics/').context['show_program'],
                        'the cache key ignored the new approval')


class TheExcelFigureStyleTest(SimpleTestCase):

    def setUp(self):
        self.source = (JS / 'excel-charts.js').read_text(encoding='utf-8')

    def test_the_palette_is_varied_and_leaves_the_old_dark_blue_behind(self):
        palette = re.findall(r"'(#[0-9A-Fa-f]{6})'", self.source.split('var INK')[0])
        self.assertGreaterEqual(len(palette), 8, 'too few colours to tell series apart')
        self.assertEqual(len(set(palette)), len(palette), 'the palette repeats a colour')
        self.assertNotIn('#4472C4', palette,
                         'the dark blue every bar used to be was asked to go')
        self.assertNotIn('#A5A5A5', palette, 'grey reads as "no data", not as a series')

    def test_one_series_is_coloured_per_category_not_all_the_same(self):
        self.assertIn('var varied = series.length === 1', self.source)
        self.assertIn('categoryColours', self.source,
                      'the table needs the per-bar colours to key its rows')

    def test_the_bars_are_square_the_way_a_spreadsheet_draws_them(self):
        self.assertIn('borderRadius: 0', self.source)

    def test_only_the_value_axis_is_ruled(self):
        self.assertRegex(self.source, r'grid:\s*\{\s*display:\s*false')

    def test_it_draws_the_data_table_itself(self):
        self.assertIn("id: 'excelDataTable'", self.source)
        self.assertIn('fillRect', self.source)
        self.assertIn('beforeLayout', self.source)
        self.assertIn('afterDraw', self.source)

    def test_every_shape_of_chart_gets_a_table_not_just_upright_bars(self):
        for drawer in ('drawColumns', 'drawRows', 'drawList'):
            self.assertIn(drawer, self.source,
                          f'{drawer} is how one kind of chart gets its numbers')
        self.assertIn("if (chart.options.indexAxis === 'y') return 'rows'", self.source)
        self.assertIn("if (type === 'pie' || type === 'doughnut') return 'list'", self.source)

    def test_line_charts_are_no_longer_offered(self):
        self.assertNotIn('function lines(', self.source,
                         'the line builder is dead code once the toggle is gone')

    def test_the_table_replaces_the_legend_rather_than_letting_it_be_cut(self):
        self.assertIn('legend.display = false', self.source)

    def test_a_pie_table_carries_the_share_as_well_as_the_count(self):
        self.assertIn("'Share'", self.source)
        self.assertIn('toFixed(1)', self.source)

    def test_a_pie_is_not_forced_square_now_that_it_carries_a_table(self):
        self.assertIn('base.aspectRatio = config.aspectRatio || 1.6', self.source)

    def test_the_reserved_table_space_can_never_swallow_the_plot(self):
        self.assertIn('chart.width * 0.4', self.source)
        self.assertIn('chart.height * 0.5', self.source)
        self.assertIn('if (!chart.width || !chart.height) return;', self.source,
                      'reserving space against a canvas of zero collapses the chart '
                      'on the next resize')

    def test_the_table_is_dropped_rather_than_squashed_when_it_cannot_fit(self):
        self.assertIn('MIN_COLUMN', self.source)
        self.assertIn('MIN_BAND', self.source)
        self.assertIn('MAX_COLUMNS', self.source)
        self.assertIn('MAX_ROWS', self.source)
        self.assertIn('MAX_LIST_ROWS', self.source)


class TheFigureFrameReachesTheAnalyticsPageTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def test_every_chart_sits_in_a_captioned_figure(self):
        from api.models import Application, StudentProfile
        student = User.objects.create_user(
            username='s1@bipsu.edu.ph', email='s1@bipsu.edu.ph', password='pw',
            first_name='S', last_name='Lim', role='student')
        profile = StudentProfile.objects.create(
            user=student, student_id='2022-00001', course='BSCE', year_level=2, gwa=1.2)
        Application.objects.create(
            student=profile, scholarship=Scholarship.objects.get(type='Academic'),
            status='Approved')

        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn('class="xl-figure"', html)
        self.assertIn('xl-figure__caption', html)
        self.assertIn('data-figure', html)
        self.assertIn('js/excel-charts', html)

    def test_no_canvas_is_left_outside_a_figure(self):
        html = self.c.get('/vpsea/analytics/').content.decode()
        for match in re.finditer(r'<canvas id="(\w+)"', html):
            before = html[:match.start()]
            self.assertIn('xl-figure', before[-400:],
                          f'{match.group(1)} is not inside a figure frame')


class TheDashboardComesFirstTest(TestCase):

    NAVS = {
        'vpsea': ('templates/vpsea/_nav.html', '/vpsea/'),
        'nsu_staff': ('templates/nsu_staff/_nav.html', '/nsu-staff/'),
        'partner': ('templates/partner/_nav.html', '/partner/'),
    }

    def test_every_portal_that_has_a_dashboard_lists_it_first(self):
        for role, (path, home) in self.NAVS.items():
            with self.subTest(portal=role):
                source = (settings.BASE_DIR / path).read_text(encoding='utf-8')
                lines = [line for line in source.splitlines()
                         if 'sidebar-link' in line]
                self.assertTrue(lines, f'{path} has no nav links at all')
                self.assertIn(f'href="{home}"', lines[0],
                              f'{role} opens on its dashboard, so it belongs at the top '
                              'of its own sidebar')

    def test_the_office_sidebar_still_carries_every_page_it_had(self):
        source = (settings.BASE_DIR / 'templates/vpsea/_nav.html').read_text(encoding='utf-8')
        for page in ('/vpsea/accounts/', '/vpsea/analytics/', '/vpsea/announcements/',
                     '/vpsea/affirmative/', '/vpsea/partners/', '/vpsea/profile/',
                     '/vpsea/renewals/', '/vpsea/reports/', '/vpsea/archives/',
                     '/vpsea/scholarships/', '/vpsea/ranking/'):
            self.assertIn(f'href="{page}"', source,
                          f'{page} fell out when the dashboard was moved')


class TheSidebarLinksDoNotNestTest(SimpleTestCase):

    NAVS = ('vpsea/_nav.html', 'nsu_staff/_nav.html', 'partner/_nav.html',
            'student/_nav.html')

    def _anchor_depths(self, html):
        depth = 0
        depths = []
        for tag in re.findall(r'</?a\b', html):
            depth += 1 if tag == '<a' else -1
            depths.append(depth)
        return depths

    def test_every_link_closes_before_the_next_one_opens(self):
        for nav in self.NAVS:
            for enrolled in (True, False):
                with self.subTest(nav=nav, enrolled=enrolled):
                    html = render_to_string(nav, {'enrolled': enrolled,
                                                  'can_apply_academic': True})
                    depths = self._anchor_depths(html)
                    self.assertTrue(depths, f'{nav} renders no links at all')
                    self.assertEqual(
                        max(depths), 1,
                        f'a link in {nav} opens inside another one, and the '
                        'browser ends the outer link early when it does')
                    self.assertEqual(depths[-1], 0,
                                     f'a link in {nav} is never closed')


class TheChartTabsAreColouredTest(SimpleTestCase):

    def setUp(self):
        self.css = CSS.read_text(encoding='utf-8')

    def test_the_toggles_are_a_pill_of_tabs(self):
        self.assertIn('.chart-tabs {', self.css)
        self.assertIn('.chart-tabs .chart-toggle-btn.active', self.css)

    def test_a_selected_tab_is_the_brand_not_a_colour_of_its_own(self):
        self.assertNotIn('--tab-solid', self.css,
                         'tabs were given their own palette once; the brand replaced it')
        rule = re.search(r'\.chart-tabs \.chart-toggle-btn\.active \{(.*?)\}',
                         self.css, re.S)
        self.assertIsNotNone(rule)
        self.assertIn('background: var(--brand)', rule.group(1))

    def test_dark_mode_still_gives_the_strip_its_own_ground(self):
        self.assertIn('html.dark .chart-tabs', self.css)


class TheStylesheetCarriesTheNewFurnitureTest(SimpleTestCase):

    def setUp(self):
        self.css = CSS.read_text(encoding='utf-8')

    def test_every_new_component_has_a_rule(self):
        for selector in ('.skip-link', '.scroll-progress', '.route-progress',
                         '.to-top', '.control-spinner', '.pw-field', '.pw-toggle',
                         '.cookie-banner', '.fab-contact', '.search-box',
                         '.faq-item', '.copy-btn', '.pill-btn',
                         '.xl-figure', '.stamp'):
            self.assertIn(selector, self.css, f'{selector} is used but never styled')

    def test_there_is_a_print_stylesheet_that_strips_the_furniture(self):
        block = re.search(r'@media print \{(.*?)\n\}\n', self.css, re.S)
        self.assertIsNotNone(block, 'no print stylesheet at all')
        body = block.group(1)
        for hidden in ('.app-sidebar', '.to-top', '.fab-contact', '.cookie-banner',
                       '.scroll-progress', '.chart-toggle-btn'):
            self.assertIn(hidden, body, f'{hidden} would still print')
        self.assertIn('@page', self.css)

    def test_spinning_is_toned_down_for_anyone_who_asked_for_less_motion(self):
        self.assertIn('@media (prefers-reduced-motion: reduce)', self.css)

    def test_the_university_yellow_is_one_value_everywhere(self):
        yellows = set(re.findall(r'--accent(?:-pure)?:\s*(#[0-9a-fA-F]{6})', self.css))
        self.assertEqual(len(yellows), 1,
                         f'the accent is defined as more than one colour: {yellows}')


class TheCacheBusterIsInStepTest(SimpleTestCase):

    def versions(self, asset):
        pattern = re.compile(re.escape(asset) + r"' %\}\?v=(\d+)")
        found = {}
        for path in template_files():
            for match in pattern.finditer(path.read_text(encoding='utf-8')):
                found.setdefault(path.name, set()).add(match.group(1))
        return found

    def test_every_template_asks_for_the_same_stylesheet_version(self):
        seen = self.versions('css/srms.css')
        numbers = {v for values in seen.values() for v in values}
        self.assertEqual(
            len(numbers), 1,
            'templates disagree on the srms.css version, so some browsers keep a '
            f'stale stylesheet: {seen}')

    def test_every_template_asks_for_the_same_version_of_a_shared_script(self):
        for name in ('js/chrome.js', 'js/loading.js', 'js/consent.js', 'js/search.js'):
            with self.subTest(script=name):
                seen = self.versions(name)
                numbers = {v for values in seen.values() for v in values}
                self.assertLessEqual(
                    len(numbers), 1,
                    f'templates disagree on the {name} version: {seen}')


class TheNewScriptsAreShippedTest(SimpleTestCase):

    def test_every_script_a_template_asks_for_exists_on_disk(self):
        wanted = set()
        for path in template_files():
            wanted |= set(re.findall(r"\{% static '(js/[\w.-]+)' %\}",
                                     path.read_text(encoding='utf-8')))
        missing = sorted(name for name in wanted
                         if not (settings.BASE_DIR / 'static' / name).exists())
        self.assertEqual(missing, [], f'asked for but not in static/: {missing}')

    def test_no_new_script_writes_inline_styles_into_the_page(self):
        for name in ('chrome.js', 'consent.js', 'search.js'):
            source = (JS / name).read_text(encoding='utf-8')
            self.assertNotIn('.style.background', source, f'{name} hard-codes a colour')
            self.assertNotIn('.style.color', source, f'{name} hard-codes a colour')
