"""Hovering a chart has to answer "which bar is this?".

The Scholars by Semester chart pinned Chart.js to ``mode: 'index'``. That mode
answers "everything at this category", which is the right question when the
chart holds several semesters and the wrong one when it holds a single one:
with one category every pointer position resolved to the same six bars, so the
tooltip read identically wherever the pointer was and named no bar in
particular. Four of those bars were also a pixel tall, which `intersect: true`
alone would not have rescued.

The rule now lives in ``excel-charts.js`` and reads the category count. These
assert that it lives there, that the count reaches it, and that no call site
pins a mode back over it — which is the shape the original defect took, and is
invisible in review.
"""

import re

from django.conf import settings
from django.test import SimpleTestCase

CHART_JS = settings.BASE_DIR / 'static' / 'js' / 'excel-charts.js'
ANALYTICS_JS = settings.BASE_DIR / 'templates' / '_analytics_js.html'

PINNED_MODE = re.compile(r'interaction:\s*\{[^}]*mode:')

INTERACTION_RULE = re.compile(
    r'base\.interaction\s*=\s*config\.interaction\s*\|\|(.{0,400})', re.S)


class TheInteractionModeIsDecidedInOnePlaceTest(SimpleTestCase):

    def setUp(self):
        self.chart_js = CHART_JS.read_text(encoding='utf-8')
        self.analytics_js = ANALYTICS_JS.read_text(encoding='utf-8')

    def rule(self):
        found = INTERACTION_RULE.search(self.chart_js)
        self.assertIsNotNone(
            found, 'excel-charts.js no longer defaults the interaction mode.')
        return found.group(1)

    def test_the_shared_builder_reads_how_many_categories_there_are(self):
        self.assertIn('config.categoryCount === 1', self.rule())

    def test_one_category_means_the_nearest_bar_rather_than_all_of_them(self):
        rule = self.rule()
        self.assertIn("mode: 'nearest'", rule)
        self.assertIn("mode: 'index'", rule)
        self.assertLess(
            rule.index("mode: 'nearest'"), rule.index("mode: 'index'"),
            'The single-category branch must come before the index default, '
            'or every chart falls back to comparing the whole category.')

    def test_the_count_reaches_the_builder_from_the_call_site(self):
        self.assertIn('settings.categoryCount', self.analytics_js)

    def test_no_chart_pins_a_mode_over_the_shared_rule(self):
        self.assertEqual(
            PINNED_MODE.findall(self.analytics_js), [],
            'A chart in _analytics_js.html pins its own interaction mode. That '
            'overrides the category-count rule in excel-charts.js, and is how '
            'the Scholars by Semester hover broke in the first place.')


class TheShareInATooltipHasAMeaningfulDenominatorTest(SimpleTestCase):

    def setUp(self):
        self.chart_js = CHART_JS.read_text(encoding='utf-8')

    def test_a_single_category_bar_is_shared_against_the_other_bars(self):
        self.assertIn('function indexTotal(', self.chart_js)
        self.assertIn('oneCategory ? indexTotal(context) : seriesTotal(context)',
                      self.chart_js,
                      'shareOfTotal divides by the sum of one dataset. With a '
                      'single category that is the bar itself, so every bar '
                      'reads 100% of its own value.')
