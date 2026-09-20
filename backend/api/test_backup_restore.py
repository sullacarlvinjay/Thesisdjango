"""The backup is only worth having if the restore has been run.

A documented procedure nobody has executed is a hope, not a recovery plan, so
these cases write a real backup, destroy the records and read them back.
"""

import gzip
import json
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from api.models import (
    Application, Scholarship, StudentProfile, SystemSettings, User,
)


class BackupTest(TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        user = User.objects.create_user(
            username='2026-0001@bipsu.edu.ph', email='2026-0001@bipsu.edu.ph',
            password='pw', first_name='Maria', last_name='Santos', role='student')
        self.profile = StudentProfile.objects.create(
            user=user, student_id='2026-0001', course='BSCS', year_level=2,
            family_income=48000)
        Application.objects.create(
            student=self.profile, scholarship=self.scholarship,
            status='Approved', term_label='26-1')

    def _backup(self, **options):
        """Write a backup and return the path to the data file."""
        call_command('backup', output=self.folder, stdout=StringIO(), **options)
        return [os.path.join(self.folder, name)
                for name in sorted(os.listdir(self.folder))
                if name.endswith('.json.gz')][-1]

    def _rows(self, path):
        """The dump's rows, as loaddata would read them."""
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            return json.load(handle)

    def test_a_backup_carries_the_records_the_office_would_need_back(self):
        rows = self._rows(self._backup())
        models = {row['model'] for row in rows}
        for wanted in ('api.user', 'api.studentprofile', 'api.application',
                       'api.scholarship', 'api.systemsettings'):
            with self.subTest(model=wanted):
                self.assertIn(wanted, models)

    def test_a_backup_leaves_out_the_tables_a_restore_must_not_overwrite(self):
        rows = self._rows(self._backup())
        models = {row['model'] for row in rows}
        for excluded in ('contenttypes.contenttype', 'auth.permission',
                         'sessions.session', 'authtoken.token'):
            with self.subTest(model=excluded):
                self.assertNotIn(excluded, models)

    def test_a_household_income_survives_the_round_trip(self):
        path = self._backup()
        StudentProfile.objects.all().delete()
        Application.objects.all().delete()
        self.assertEqual(StudentProfile.objects.count(), 0)

        call_command('restore', path, yes=True, stdout=StringIO())

        restored = StudentProfile.objects.get(student_id='2026-0001')
        self.assertEqual(restored.family_income, 48000)
        self.assertEqual(restored.user.get_full_name(), 'Maria Santos')

    def test_an_approved_award_survives_the_round_trip(self):
        path = self._backup()
        Application.objects.all().delete()

        call_command('restore', path, yes=True, stdout=StringIO())

        award = Application.objects.get()
        self.assertEqual(award.status, 'Approved')
        self.assertEqual(award.term_label, '26-1')
        self.assertEqual(award.student.student_id, '2026-0001')

    def test_a_restore_refuses_to_run_without_being_told_twice(self):
        path = self._backup()
        StudentProfile.objects.all().delete()

        with self.assertRaises(CommandError) as refused:
            call_command('restore', path, stdout=StringIO())
        self.assertIn('--yes', str(refused.exception))
        self.assertEqual(StudentProfile.objects.count(), 0)

    def test_a_restore_from_a_missing_file_says_so_rather_than_crashing(self):
        with self.assertRaises(CommandError) as refused:
            call_command('restore', os.path.join(self.folder, 'nope.json.gz'),
                         yes=True, stdout=StringIO())
        self.assertIn('no such file', str(refused.exception))

    def test_the_manifest_names_every_upload_the_database_expects(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from api.models import ApplicationDocument

        ApplicationDocument.objects.create(
            application=Application.objects.get(), name='Certificate Of Grades',
            file=SimpleUploadedFile('cog.pdf', b'%PDF-1.4',
                                    content_type='application/pdf'))

        call_command('backup', output=self.folder, stdout=StringIO())
        manifest = [os.path.join(self.folder, name)
                    for name in sorted(os.listdir(self.folder))
                    if name.endswith('.manifest.txt')][-1]
        text = open(manifest, encoding='utf-8').read()
        self.assertIn('api.ApplicationDocument.file', text)
        self.assertIn('cog', text)

    def test_the_manifest_is_discovered_rather_than_hand_listed(self):
        from api.management.commands.backup import _file_fields

        from api.models import ApplicationDocument, ScholarListImport

        owners = {model for model, _field in _file_fields()}
        self.assertIn(ApplicationDocument, owners)
        self.assertIn(ScholarListImport, owners)
