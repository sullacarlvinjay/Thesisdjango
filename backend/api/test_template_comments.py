"""No template comment ever reaches the page.

Django's ``{# ... #}`` is a single-line comment. When the opener and the closer
land on different lines the lexer never matches it, and the prose is printed
into the page — which is how a paragraph explaining the archive table's markup
came to be rendered to the office above the table it described. Multi-line
comments have to be ``{% comment %} ... {% endcomment %}``.

Nothing about that is visible in a view test that checks for the values it
expects to find, so this checks the templates themselves.
"""
import os
import re

from django.conf import settings
from django.test import TestCase


def template_files():
    for root in settings.TEMPLATES[0]['DIRS']:
        for folder, _, files in os.walk(root):
            for name in files:
                if name.endswith('.html'):
                    yield os.path.join(folder, name)


class TemplateCommentsAreClosedOnTheirOwnLineTest(TestCase):

    def test_no_template_opens_a_comment_it_does_not_close(self):
        offenders = []
        for path in template_files():
            with open(path, encoding='utf-8') as handle:
                for number, line in enumerate(handle, 1):
                    if line.count('{#') != line.count('#}'):
                        offenders.append(f'{os.path.relpath(path)}:{number}')
        self.assertEqual(
            offenders, [],
            'These lines open or close a {# #} comment across a line break, so '
            'Django prints them onto the page instead of treating them as a '
            'comment. Use {% comment %} ... {% endcomment %} for anything that '
            'spans more than one line:\n  ' + '\n  '.join(offenders))

    def test_the_archive_table_renders_no_prose_from_its_own_markup(self):
        """The page that showed it, checked end to end rather than by eye."""
        from api.models import Scholarship, SystemSettings, User
        from django.test import Client

        SystemSettings.objects.get_or_create(pk=1)
        Scholarship.objects.create(name='Academic Scholarship', type='Academic',
                                   category='application', description='x',
                                   eligibility='x', requirements=[])
        User.objects.create_user(username='v@bipsu.edu.ph', email='v@bipsu.edu.ph',
                                 password='pw', first_name='V', last_name='Officer',
                                 role='vpsea')
        c = Client()
        self.assertTrue(c.login(email='v@bipsu.edu.ph', password='pw'))

        for url, params in (('/vpsea/archives/', {'type': 'Academic'}),
                            ('/vpsea/scholarships/add/', {}),
                            ('/register/', {})):
            html = c.get(url, params).content.decode()
            self.assertNotIn('{#', html, f'{url} printed a comment opener')
            self.assertNotIn('#}', html, f'{url} printed a comment closer')
            # Phrases that can only have come out of a template comment. Kept
            # narrow on purpose: "the browser" reads like commentary but is also
            # the document viewer's own message to the reader.
            for giveaway in ('hand-written', 'api/scholar_columns.py',
                             'row markup', 'a form inside a form',
                             'My Profile offers'):
                self.assertNotIn(giveaway, html,
                                 f'{url} printed template commentary: {giveaway!r}')
