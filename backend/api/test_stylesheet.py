import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS = settings.BASE_DIR / 'static' / 'css' / 'srms.css'


def template_files():
    for root in settings.TEMPLATES[0]['DIRS']:
        yield from Path(root).rglob('*.html')


def without_comments(text):
    return re.sub(r'/\*.*?\*/', '', text, flags=re.S)


class StylesheetBracesBalanceTest(SimpleTestCase):

    def setUp(self):
        self.css = without_comments(CSS.read_text(encoding='utf-8'))

    def test_no_block_closes_before_it_opens(self):
        depth = 0
        for index, char in enumerate(self.css):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth < 0:
                    line = self.css[:index].count('\n') + 1
                    self.fail(
                        f'A closing brace at roughly line {line} of srms.css '
                        'closes a block that was never opened. Everything after '
                        'it is discarded by the browser without a word.')

    def test_every_block_is_closed(self):
        depth = self.css.count('{') - self.css.count('}')
        self.assertEqual(depth, 0,
                         f'srms.css leaves {depth} block(s) open. The rules that '
                         'follow are swallowed into the last one.')


class TheLandingHeroFillsTheScreenTest(SimpleTestCase):
    def setUp(self):
        self.css = CSS.read_text(encoding='utf-8')

    def test_the_hero_is_sized_against_the_viewport(self):
        rule = re.search(r'\.hero-landing\s*\{(.*?)\}', self.css, re.S)
        self.assertIsNotNone(rule, '.hero-landing has no rule at all')
        body = rule.group(1)
        self.assertIn('min-height: calc(100vh - var(--nav-h))', body)
        self.assertIn('min-height: calc(100dvh - var(--nav-h))', body,
                      'the dvh line is what keeps it honest on a phone')

    def test_the_variable_it_measures_against_is_declared(self):
        self.assertRegex(self.css, r'--nav-h:\s*calc\(4rem \+ 1px\)')

    def test_only_a_short_landscape_window_turns_it_off(self):
        shortened = re.search(
            r'@media \(max-height: 560px\) \{(.*?)\n\}', self.css, re.S)
        self.assertIsNotNone(shortened)
        self.assertIn('.hero-landing { min-height: 0; }', shortened.group(1))


class EveryBadgeVariantTemplatesAskForExistsTest(SimpleTestCase):
    def setUp(self):
        self.css = CSS.read_text(encoding='utf-8')

    def defined(self):
        return set(re.findall(r'\.(badge-[a-z0-9-]+)', self.css))

    def used(self):
        names = set()
        for path in template_files():
            names |= set(re.findall(
                r'badge-[a-z0-9-]+', path.read_text(encoding='utf-8')))
        return names

    def test_no_template_asks_for_a_badge_the_stylesheet_does_not_define(self):
        missing = sorted(self.used() - self.defined())
        self.assertEqual(missing, [], f'used in a template, no CSS rule: {missing}')
