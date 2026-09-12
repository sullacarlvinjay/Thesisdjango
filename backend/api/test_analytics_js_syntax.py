"""The analytics page's inline script has to parse, in every filter state.

Every chart on the page is built by one <script> block. A JavaScript error
anywhere in it stops the rest of the block dead, so a single bad line does not
cost one chart — it costs every chart below it, and the page comes up with
empty cards and nothing in the console to explain them to whoever is looking.

The block is assembled by the template out of office-entered programme names
and per-filter conditionals, so it is generated code, and generated code is
worth parsing before a browser has to.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from django.test import Client, TestCase

from api.models import (
    Application, ImportedScholar, Scholarship, StudentProfile, SystemSettings,
    User,
)

NODE = shutil.which('node')

# The chart block is the one that pulls in Chart.js.
SCRIPTS = re.compile(r'<script>(.*?)</script>', re.S)


@unittest.skipIf(NODE is None, 'node is not installed')
class AnalyticsScriptParsesTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        for stype in ('Academic', 'TDP', 'CHED'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype, category='application',
                description='x', eligibility='x', requirements=[])
        # A programme named by the office, with the punctuation an office uses.
        Scholarship.objects.create(
            name="Governor's Award", type="Governor's Award",
            category='application', description='x', eligibility='x',
            requirements=[])
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def award(self, n, stype, course='BSCE', gwa=1.2):
        user = User.objects.create_user(
            username=f's{n}@bipsu.edu.ph', email=f's{n}@bipsu.edu.ph',
            password='pw', first_name=f'S{n}', last_name=f'Lim{n}', role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id=f'2022-{n:05d}', course=course, year_level=2,
            gwa=gwa)
        return Application.objects.create(
            student=profile, scholarship=Scholarship.objects.get(type=stype),
            status='Approved')

    def assertParses(self, **params):
        html = self.c.get('/vpsea/analytics/', params).content.decode()
        blocks = [b for b in SCRIPTS.findall(html) if 'new Chart(' in b
                  or 'chart-png-btn' in b]
        self.assertTrue(blocks, f'no chart script rendered for {params}')
        source = '\n'.join(blocks)
        # Written out rather than piped: `node --check` takes a filename,
        # and given none it sits waiting on a stdin it never reads.
        handle, path = tempfile.mkstemp(suffix='.js')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as fh:
                fh.write(source)
            # --check parses without running: nothing here needs a DOM, and
            # a ReferenceError for `document` would say nothing about syntax.
            proc = subprocess.run([NODE, '--check', path],
                                  capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(path)
        self.assertEqual(proc.returncode, 0,
                         f'{params} produced unparseable JS: {proc.stderr}')

    def test_it_parses_with_nothing_on_record(self):
        self.assertParses()

    def test_it_parses_with_scholars_across_programmes(self):
        self.award(1, 'Academic')
        self.award(2, 'TDP', course='BSIT')
        self.award(3, 'CHED', course='BSED')
        self.assertParses()

    def test_it_parses_under_every_programme_filter(self):
        self.award(1, 'Academic')
        self.award(2, 'TDP', course='BSIT')
        ImportedScholar.objects.create(
            scholarship_type='CHED', term_label='25-2', last_name='Cruz',
            first_name='Juan', course='BSCE', year_level=2)
        for stype in ('', 'Academic', 'TDP', 'CHED', "Governor's Award"):
            with self.subTest(stype=stype):
                self.assertParses(stype=stype)

    def test_a_programme_name_with_an_apostrophe_survives_the_round_trip(self):
        """The office types these names, and JS strings are quoted with '."""
        self.award(1, "Governor's Award")
        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn('programChart', html)
        self.assertParses()
