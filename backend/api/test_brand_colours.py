import colorsys
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS = settings.BASE_DIR / 'static' / 'css' / 'srms.css'

HEX = re.compile(r'#([0-9a-fA-F]{6})\b')

BLUE = (200, 265)
YELLOW = (40, 68)
RED_LOW = 14
RED_HIGH = 340

FLAT = 0.16
NEAR_BLACK = 0.06
NEAR_WHITE = 0.965


def families(value):
    red, green, blue = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(red, green, blue)
    hue *= 360
    if sat < FLAT or light < NEAR_BLACK or light > NEAR_WHITE:
        return 'neutral'
    if BLUE[0] <= hue <= BLUE[1]:
        return 'blue'
    if YELLOW[0] <= hue <= YELLOW[1]:
        return 'yellow'
    if hue >= RED_HIGH or hue <= RED_LOW:
        return 'red'
    return 'off-brand'


def painted_files():
    yield CSS
    for root in settings.TEMPLATES[0]['DIRS']:
        yield from sorted(Path(root).rglob('*.html'))


def offenders():
    found = []
    for path in painted_files():
        for number, line in enumerate(path.read_text(encoding='utf-8').split('\n'), 1):
            for value in HEX.findall(line):
                if families(value.lower()) == 'off-brand':
                    found.append(f'{path.name}:{number} #{value.lower()}')
    return found


class TheInterfaceStaysOnBiPSUColoursTest(SimpleTestCase):

    def test_nothing_is_painted_outside_blue_yellow_red_or_grey(self):
        found = offenders()
        self.assertEqual(
            found, [],
            'BiPSU is blue and yellow. Red is kept only so an error still reads as '
            'an error, and greys carry text and surfaces. Anything else — a green '
            'tick, an orange pill, a purple tab — breaks the consistency the whole '
            'system is judged on:\n  ' + '\n  '.join(found))

    def test_the_two_brand_colours_are_what_the_tokens_say(self):
        css = CSS.read_text(encoding='utf-8')
        root = css[css.index(':root {'):css.index('body {')]
        self.assertRegex(root, r'--brand:\s*#0000d4')
        self.assertRegex(root, r'--accent:\s*#fdea2b')

    def test_a_status_never_reads_as_green_or_amber(self):
        css = CSS.read_text(encoding='utf-8')
        for token in ('--ok', '--warn', '--info'):
            for value in re.findall(token + r':\s*(#[0-9a-fA-F]{6})', css):
                with self.subTest(token=token, value=value):
                    self.assertIn(families(value[1:].lower()), ('blue', 'yellow', 'neutral'),
                                  f'{token} is {value}, which is neither blue nor yellow')

    def test_danger_is_still_red_in_both_themes(self):
        css = CSS.read_text(encoding='utf-8')
        values = re.findall(r'--danger:\s*(#[0-9a-fA-F]{6})', css)
        self.assertGreaterEqual(len(values), 2, 'light and dark both need a danger colour')
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(families(value[1:].lower()), 'red',
                                 'an error that is not red is an error people miss')


class TheChartTabsUseTheBrandTest(SimpleTestCase):

    def setUp(self):
        self.css = CSS.read_text(encoding='utf-8')

    def test_the_tabs_carry_no_colour_of_their_own(self):
        self.assertNotIn('--tab-solid', self.css,
                         'the per-tab palette was replaced by the brand')
        self.assertNotIn('--tab-ink', self.css)

    def test_a_selected_tab_is_brand_blue(self):
        rule = re.search(r'\.chart-tabs \.chart-toggle-btn\.active \{(.*?)\}',
                         self.css, re.S)
        self.assertIsNotNone(rule, 'the active tab has no rule')
        self.assertIn('background: var(--brand)', rule.group(1))

    def test_the_analytics_series_palette_is_left_alone(self):
        chart = (settings.BASE_DIR / 'static' / 'js' / 'excel-charts.js').read_text(
            encoding='utf-8')
        palette = re.findall(r"'(#[0-9A-Fa-f]{6})'", chart.split('var INK')[0])
        self.assertGreaterEqual(len(palette), 8,
                                'charts are allowed their own colours so series can '
                                'be told apart; only the interface is restricted')
