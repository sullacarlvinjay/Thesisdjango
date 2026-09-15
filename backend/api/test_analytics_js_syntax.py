import json
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

SCRIPTS = re.compile(r'<script>(.*?)</script>', re.S)


@unittest.skipIf(NODE is None, 'node is not installed')
class AnalyticsScriptParsesTest(TestCase):

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        for stype in ('Academic', 'TDP', 'CHED'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype, category='application',
                description='x', eligibility='x', requirements=[])
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
        handle, path = tempfile.mkstemp(suffix='.js')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as fh:
                fh.write(source)
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
        self.award(1, "Governor's Award")
        html = self.c.get('/vpsea/analytics/').content.decode()
        self.assertIn("Governor&#x27;s Award", html)
        self.assertParses()


@unittest.skipIf(NODE is None, 'node is not installed')
class LegendLabelsFitTest(AnalyticsScriptParsesTest):
    def run_legend(self, labels):
        html = self.c.get('/vpsea/analytics/').content.decode()
        block = next(b for b in SCRIPTS.findall(html) if 'legendText' in b)
        start = block.index('const DEGREE_PREFIX')
        end = block.index('function shortLegendLabels')
        source = (block[start:end]
                  + os.linesep
                  + 'console.log(JSON.stringify('
                  + json.dumps(labels) + '.map(legendText)));')
        handle, path = tempfile.mkstemp(suffix='.js')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as fh:
                fh.write(source)
            proc = subprocess.run([NODE, path], capture_output=True, text=True,
                                  encoding='utf-8', timeout=60)
        finally:
            os.unlink(path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    REPORTED = [
        'Bachelor of Science in Business Administration',
        'Bachelor of Science in Hospitality Management',
        'Bachelor of Science in Industrial Technology',
        'Bachelor of Secondary Education',
        'Bachelor of Science in Criminology',
        'Bachelor of Science in Information Systems',
        'Bachelor of Science in Tourism Management',
        'Bachelor of Science in Computer Science',
        'Bachelor of Arts in Economics',
        'Bachelor of Arts in Communication',
        'Bachelor of Science in Civil Engineering',
        'Bachelor of Science in Nursing',
    ]

    def test_every_reported_label_fits_without_being_cut(self):
        for label, short in zip(self.REPORTED, self.run_legend(self.REPORTED)):
            with self.subTest(label=label):
                self.assertNotIn('…', short)
                self.assertLessEqual(len(short), 26)

    def test_the_labels_still_tell_the_courses_apart(self):
        shortened = self.run_legend(self.REPORTED)
        self.assertEqual(len(set(shortened)), len(self.REPORTED))
        for short in shortened:
            with self.subTest(short=short):
                self.assertNotIn('Bachelor', short)

    def test_a_course_stored_as_an_acronym_is_left_alone(self):
        acronyms = ['BSCS', 'BSEd - Mathematics', 'BSIT - Culinary Technology']
        self.assertEqual(self.run_legend(acronyms), acronyms)

    def test_a_name_too_long_even_when_shortened_is_cut_with_an_ellipsis(self):
        long_name = 'Bachelor of Science in Hotel and Restaurant Management Technology'
        short = self.run_legend([long_name])[0]
        self.assertTrue(short.endswith('…'))
        self.assertEqual(len(short), 26)
        self.assertTrue(short.startswith('Hotel'))
