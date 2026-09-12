"""No template starts with a byte order mark.

A UTF-8 BOM is invisible in an editor and catastrophic in a browser. It is not
whitespace to the HTML parser, so a document beginning with one is a document
that begins with *content*: the parser closes ``<head>`` before it has opened,
drops the page into quirks mode, and moves every ``<meta>``, ``<title>``,
``<link>`` and ``<script>`` into the body. The BOM itself then lays out as an
ordinary character and reserves a line box for itself — a 24-pixel band above
the page that scrolls with it, which is what this was found as: a gap at the
top of every signed-in page, and a page that kept scrolling a little past its
own content.

Windows editors add the mark on save without saying so, which is how fifty-two
of these templates came to carry one. The check is the file's bytes rather than
a rendered page because that is where it can be seen at all.

Partials matter as much as the pages that extend base.html: ``{% include %}``
splices the mark into the middle of the document, where it is a stray character
inside a nav or a table rather than a parse error, and just as invisible.
"""
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
        """One spliced in mid-file is a stray zero-width character on the page
        rather than a parse error, and no more visible in an editor."""
        offenders = []
        for path in template_files():
            text = open(path, encoding='utf-8-sig').read()
            if '\ufeff' in text:
                offenders.append(f'{os.path.relpath(path)}:{text.index(chr(0xFEFF))}')
        self.assertEqual(offenders, [], 'U+FEFF found inside these templates: '
                         + ', '.join(offenders))


class ThePageParsesInStandardsModeTest(SimpleTestCase):
    """The symptom, checked on the rendered bytes rather than on the sources.

    ``<!DOCTYPE html>`` has to be the very first thing a browser reads. Anything
    at all in front of it — a mark, a stray space from a template tag — and the
    doctype is ignored.
    """

    def test_the_login_page_begins_with_its_doctype(self):
        from django.test import Client
        html = Client().get('/login/').content
        self.assertTrue(html.startswith(b'<!DOCTYPE html>'),
                        f'The page starts with {html[:20]!r}, not its doctype.')
