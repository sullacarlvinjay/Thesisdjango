import codecs
import os

from django.conf import settings
from django.test import SimpleTestCase


def template_files():
    for root in settings.TEMPLATES[0]['DIRS']:
        for folder, _, files in os.walk(root):
            for name in files:
                if name.endswith('.html'):
                    yield os.path.join(folder, name)


class NoTemplateCarriesAByteOrderMarkTest(SimpleTestCase):

    def test_no_template_file_starts_with_one(self):
        offenders = [os.path.relpath(path) for path in template_files()
                     if open(path, 'rb').read(3) == codecs.BOM_UTF8]
        self.assertEqual(
            offenders, [],
            'These templates start with a UTF-8 byte order mark. Save them as '
            'UTF-8 without BOM — the mark is not whitespace to a browser, and '
            'a page that begins with one parses in quirks mode with its whole '
            '<head> moved into the <body>:\n  ' + '\n  '.join(offenders))

    def test_the_mark_does_not_hide_further_into_a_template_either(self):
        offenders = []
        for path in template_files():
            text = open(path, encoding='utf-8-sig').read()
            if '\ufeff' in text:
                offenders.append(f'{os.path.relpath(path)}:{text.index(chr(0xFEFF))}')
        self.assertEqual(offenders, [], 'U+FEFF found inside these templates: '
                         + ', '.join(offenders))


class ThePageParsesInStandardsModeTest(SimpleTestCase):
    def test_the_login_page_begins_with_its_doctype(self):
        from django.test import Client
        html = Client().get('/login/').content
        self.assertTrue(html.startswith(b'<!DOCTYPE html>'),
                        f'The page starts with {html[:20]!r}, not its doctype.')
