import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

STYLESHEET = Path(settings.BASE_DIR) / 'static' / 'css' / 'srms.css'

AA_NORMAL = 4.5
AA_LARGE = 3.0

SURFACES = ('bg', 'surface', 'surface-2', 'surface-sunken')

TEXT_ON_SURFACE = ('text', 'text-soft', 'text-muted')

PAIRED = (
    ('ok', 'ok-bg'),
    ('warn', 'warn-bg'),
    ('info', 'info-bg'),
    ('danger', 'danger-bg'),
    ('on-accent', 'accent'),
    ('on-brand', 'brand'),
)


def _tokens(selector):
    """Custom properties declared in one rule of the stylesheet."""
    css = STYLESHEET.read_text(encoding='utf-8')
    start = css.find(selector)
    if start == -1:
        raise AssertionError(f'{selector} is no longer in the stylesheet')
    opening = css.index('{', start)
    closing = css.index('}', opening)
    return {name: value.strip() for name, value in
            re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', css[opening:closing])}


def _channels(value):
    value = value.strip().lstrip('#')
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _relative_luminance(colour):
    def channel(raw):
        raw /= 255
        return raw / 12.92 if raw <= 0.03928 else ((raw + 0.055) / 1.055) ** 2.4
    red, green, blue = (channel(c) for c in _channels(colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground, background):
    """WCAG 2.1 contrast ratio between two hex colours."""
    first = _relative_luminance(foreground)
    second = _relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


class ContrastTestCase(SimpleTestCase):
    """Assert the palette against WCAG AA, rather than trusting it by eye.

    Contrast is arithmetic, so it can be checked rather than reviewed. These
    cases read the tokens straight out of the stylesheet, so a palette change
    that drops a pair below the threshold fails here instead of reaching
    someone who cannot read the result.

    Hex literals only. A token defined with ``color-mix`` or ``rgba`` is
    skipped, because its rendered value depends on what it is composited over.
    """

    selector = ':root {'
    inherits = None
    label = 'light'

    def palette(self):
        tokens = dict(_tokens(self.inherits)) if self.inherits else {}
        tokens.update(_tokens(self.selector))
        return tokens

    def _hex(self, tokens, name):
        value = tokens.get(f'--{name}', '')
        return value if value.startswith('#') else None

    def test_body_text_clears_aa_on_every_surface(self):
        tokens = self.palette()
        for text in TEXT_ON_SURFACE:
            foreground = self._hex(tokens, text)
            if foreground is None:
                continue
            for surface in SURFACES:
                background = self._hex(tokens, surface)
                if background is None:
                    continue
                with self.subTest(theme=self.label, text=text, on=surface):
                    ratio = contrast(foreground, background)
                    self.assertGreaterEqual(
                        ratio, AA_NORMAL,
                        f'--{text} ({foreground}) on --{surface} '
                        f'({background}) is {ratio:.2f}:1, below the '
                        f'{AA_NORMAL}:1 WCAG AA minimum for body text')

    def test_status_colours_clear_aa_against_their_own_background(self):
        tokens = self.palette()
        for foreground_name, background_name in PAIRED:
            foreground = self._hex(tokens, foreground_name)
            background = self._hex(tokens, background_name)
            if foreground is None or background is None:
                continue
            with self.subTest(theme=self.label, pair=foreground_name):
                ratio = contrast(foreground, background)
                self.assertGreaterEqual(
                    ratio, AA_NORMAL,
                    f'--{foreground_name} ({foreground}) on '
                    f'--{background_name} ({background}) is {ratio:.2f}:1, '
                    f'below the {AA_NORMAL}:1 WCAG AA minimum')

    def test_the_brand_colour_is_legible_on_the_page_background(self):
        tokens = self.palette()
        brand = self._hex(tokens, 'brand')
        for surface in ('bg', 'surface'):
            background = self._hex(tokens, surface)
            if brand is None or background is None:
                continue
            with self.subTest(theme=self.label, on=surface):
                ratio = contrast(brand, background)
                self.assertGreaterEqual(
                    ratio, AA_LARGE,
                    f'--brand ({brand}) on --{surface} ({background}) is '
                    f'{ratio:.2f}:1, below {AA_LARGE}:1 even for large text')


class LightThemeContrastTest(ContrastTestCase):
    selector = ':root {'
    label = 'light'


class DarkThemeContrastTest(ContrastTestCase):
    selector = '.dark {'
    inherits = ':root {'
    label = 'dark'


class DarkPortalContrastTest(ContrastTestCase):
    """The portals override the dark palette again, so they need their own pass."""

    selector = ".dark[data-portal='student']"
    inherits = '.dark {'
    label = 'dark portal'
