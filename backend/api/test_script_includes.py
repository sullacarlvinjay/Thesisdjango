"""No page loads the same script twice.

The scholarship-type picker on the archive pages did nothing when clicked.
``dl-menu.js`` was included by ``base.html`` and again by each archive
template, so every button carried two click handlers: the first opened the
menu, the second closed it, and the net effect of a click was nothing at all.

It is the same failure as two scripts reading one attribute — the second
handler undoes the first — and it is invisible in review, so it is asserted
here instead.
"""

import glob
import pathlib
import re

from django.conf import settings
from django.test import SimpleTestCase

SCRIPT = re.compile(r"js/([\w.-]+\.js)")

EXTENDS_BASE = re.compile(r"""\{%\s*extends\s*["']base\.html["']\s*%\}""")


def scripts_in(path):
    """Every ``static/js`` file a template pulls in."""
    return SCRIPT.findall(pathlib.Path(path).read_text(encoding='utf-8'))


def templates_extending_base():
    """Templates that inherit the shared chrome."""
    for path in sorted(glob.glob(
            str(settings.BASE_DIR / 'templates/**/*.html'), recursive=True)):
        text = pathlib.Path(path).read_text(encoding='utf-8')
        if EXTENDS_BASE.search(text):
            yield path


class NoScriptIsLoadedTwiceTest(SimpleTestCase):

    def setUp(self):
        self.base = set(scripts_in(settings.BASE_DIR / 'templates/base.html'))

    def test_base_loads_the_shared_scripts(self):
        self.assertIn('dl-menu.js', self.base,
                      'base.html is where the shared chrome scripts belong')

    def test_no_child_template_repeats_a_script_base_already_loads(self):
        for path in templates_extending_base():
            repeated = sorted({name for name in scripts_in(path)
                               if name in self.base})
            with self.subTest(template=pathlib.Path(path).name):
                self.assertEqual(
                    repeated, [],
                    f'{pathlib.Path(path).name} loads {repeated} on top of '
                    "base.html's copy, so every handler is bound twice")

    def test_no_single_template_lists_one_script_twice(self):
        for path in sorted(glob.glob(
                str(settings.BASE_DIR / 'templates/**/*.html'), recursive=True)):
            names = scripts_in(path)
            with self.subTest(template=pathlib.Path(path).name):
                self.assertEqual(
                    len(names), len(set(names)),
                    f'{pathlib.Path(path).name} lists the same script twice')


class TheMenuBindsOnceTest(SimpleTestCase):

    def test_the_dropdown_script_refuses_to_bind_a_second_time(self):
        """A template mistake must not be able to break the menu again."""
        source = (settings.BASE_DIR / 'static/js/dl-menu.js').read_text(
            encoding='utf-8')
        self.assertIn('__dlMenuBound', source)
        guard = source.index('__dlMenuBound')
        binding = source.index("addEventListener('click'")
        self.assertLess(guard, binding,
                        'the guard has to run before anything is bound')

    def test_one_script_implements_the_dropdown_and_no_other(self):
        owners = [pathlib.Path(path).name for path in glob.glob(
            str(settings.BASE_DIR / 'static/js/*.js'))
            if 'data-dl-menu' in pathlib.Path(path).read_text(encoding='utf-8')]
        self.assertEqual(owners, ['dl-menu.js'])

    def test_the_click_toggles_rather_than_being_bound_per_page(self):
        source = (settings.BASE_DIR / 'static/js/dl-menu.js').read_text(
            encoding='utf-8')
        self.assertEqual(source.count("classList.toggle('is-open')"), 1,
                         'two toggles in one handler would cancel out')
