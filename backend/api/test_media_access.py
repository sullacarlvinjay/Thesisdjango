"""Who may read an uploaded file.

Before this, /media/ went through ``static()``: every document was readable by
anyone holding the URL, and the whole tree vanished once DEBUG was off. These
tests pin both halves of the replacement — that the right people still get their
files, and that nobody else does.

MEDIA_ROOT is redirected into a temporary directory for the duration, so a run
cannot deposit fixtures in the real media folder.
"""

import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import (
    Application, ApplicationDocument, Scholarship, ScholarshipLinkRequest,
    StudentProfile, SystemSettings,
)

User = get_user_model()

MEDIA = tempfile.mkdtemp(prefix='srms-media-test-')


def _student(email, student_id):
    user = User.objects.create_user(
        username=email, email=email, password='pw-for-test-only', role='student')
    profile = StudentProfile.objects.create(
        user=user, student_id=student_id, course='BSIT', year_level=2)
    return user, profile


def _scholarship():
    return Scholarship.objects.create(
        name='Academic Scholarship', type='Academic', category='application',
        description='x', eligibility='x', requirements=[],
    )


@override_settings(MEDIA_ROOT=MEDIA)
class MediaAccessTest(TestCase):

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.owner_user, self.owner = _student('owner@bipsu.edu.ph', 'S-1001')
        self.other_user, self.other = _student('other@bipsu.edu.ph', 'S-1002')

        self.office = User.objects.create_user(
            username='vpsea@bipsu.edu.ph', email='vpsea@bipsu.edu.ph',
            password='pw-for-test-only', role='vpsea')

        application = Application.objects.create(
            student=self.owner, scholarship=_scholarship(), status='Pending',
            form_data={})
        self.doc = ApplicationDocument.objects.create(
            application=application,
            name='Certificate of Grades',
            file=SimpleUploadedFile('cog.pdf', b'%PDF-1.4 owned', 'application/pdf'),
        )
        self.url = '/media/' + self.doc.file.name

    # ── the file reaches the people it should ────────────────────────────────

    def test_the_student_who_uploaded_it_can_read_it(self):
        self.client.force_login(self.owner_user)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_the_reviewing_office_can_read_any_document(self):
        self.client.force_login(self.office)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    # ── and nobody else ──────────────────────────────────────────────────────

    def test_a_signed_out_visitor_holding_the_url_gets_nothing(self):
        """The old static() route served this to anyone who asked."""
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_another_student_cannot_read_someone_elses_document(self):
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_refusal_is_404_not_403_so_it_does_not_confirm_the_file_exists(self):
        self.client.force_login(self.other_user)
        real = self.client.get(self.url)
        invented = self.client.get('/media/documents/no-such-file.pdf')
        self.assertEqual(real.status_code, invented.status_code)

    # ── office-only artefacts ────────────────────────────────────────────────

    def test_students_cannot_reach_office_imports(self):
        self.client.force_login(self.owner_user)
        self.assertEqual(self.client.get('/media/rollovers/list.xlsx').status_code, 404)

    # ── branding stays public ────────────────────────────────────────────────

    def test_the_logo_is_readable_signed_out_because_the_login_page_needs_it(self):
        from django.core.files.storage import default_storage
        name = default_storage.save('logos/test-logo.png', SimpleUploadedFile(
            'test-logo.png', b'\x89PNG\r\n\x1a\n', 'image/png'))
        self.assertEqual(self.client.get('/media/' + name).status_code, 200)

    # ── path handling ────────────────────────────────────────────────────────

    def test_branding_is_read_from_disk_not_from_the_upload_bucket(self):
        """In production default_storage is Supabase, which has no logos in it.

        The university's branding ships with the code, so it must come off the
        filesystem regardless of where uploads are kept. Standing in for the
        bucket is a storage that fails loudly if anything asks it for a logo.
        """
        from django.core.files.storage import default_storage

        name = default_storage.save('logos/from-disk.png', SimpleUploadedFile(
            'from-disk.png', b'\x89PNG\r\n\x1a\n', 'image/png'))

        def refuse(*a, **kw):
            raise AssertionError('branding must not be fetched from the upload bucket')

        with mock.patch.object(default_storage, 'open', refuse), \
                mock.patch.object(default_storage, 'exists', refuse):
            self.assertEqual(self.client.get('/media/' + name).status_code, 200)

    def test_a_path_climbing_out_of_media_root_is_refused(self):
        self.client.force_login(self.office)
        self.assertEqual(
            self.client.get('/media/../config/settings.py').status_code, 404)

    def test_an_unrecognised_prefix_is_refused_rather_than_guessed(self):
        """A new FileField is invisible until media_views learns about it.

        Failing closed is the point: the alternative is a field that silently
        serves to everyone the day it is added.
        """
        self.client.force_login(self.owner_user)
        self.assertEqual(self.client.get('/media/somewhere-new/x.pdf').status_code, 404)


@override_settings(MEDIA_ROOT=MEDIA)
class LinkRequestProofAccessTest(TestCase):
    """Link-request proofs are the largest folder on disk, so they get their own."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        self.owner_user, self.owner = _student('claimant@bipsu.edu.ph', 'S-2001')
        self.snooper_user, _ = _student('snooper@bipsu.edu.ph', 'S-2002')
        self.request_row = ScholarshipLinkRequest.objects.create(
            student=self.owner,
            scholarship_type='TES',
            proof_document=SimpleUploadedFile(
                'award.pdf', b'%PDF-1.4 award', 'application/pdf'),
        )
        self.url = '/media/' + self.request_row.proof_document.name

    def test_the_claimant_can_read_their_own_proof(self):
        self.client.force_login(self.owner_user)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_another_student_cannot(self):
        self.client.force_login(self.snooper_user)
        self.assertEqual(self.client.get(self.url).status_code, 404)
