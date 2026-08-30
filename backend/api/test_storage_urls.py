"""Where a document link points when uploads live in Supabase.

The bug these cover shipped silently. Everything worked on a laptop, because
FileSystemStorage returns ``/media/…`` and that is the view which checks who is
asking. Turning on Supabase Storage changed ``{{ doc.file.url }}`` to the
bucket's own address, and the browser started talking to Supabase directly —
past every permission check in api.media_views.

It surfaced only as an S3 error, ``AccessDenied: Missing signature``, because
the bucket is private. On a public bucket there would have been no error at
all: the documents would simply have been served to anyone holding a link.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .storage import ProtectedS3Storage

# Credentials are never used: every assertion below is about the address a URL
# has, and none of them opens a connection.
S3_SETTINGS = {
    'STORAGES': {
        'default': {
            'BACKEND': 'api.storage.ProtectedS3Storage',
            'OPTIONS': {
                'endpoint_url': 'https://example.supabase.co/storage/v1/s3',
                'region_name': 'ap-northeast-1',
                'access_key': 'not-a-real-key',
                'secret_key': 'not-a-real-secret',
                'bucket_name': 'srms-media',
                'default_acl': None,
                'querystring_auth': False,
            },
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
}


class ProtectedS3StorageUrlTest(TestCase):

    def setUp(self):
        self.storage = ProtectedS3Storage(
            bucket_name='srms-media',
            endpoint_url='https://example.supabase.co/storage/v1/s3',
            access_key='not-a-real-key',
            secret_key='not-a-real-secret',
        )

    def test_the_url_points_at_our_own_view_not_the_bucket(self):
        url = self.storage.url('documents/cog.pdf')
        self.assertEqual(url, '/media/documents/cog.pdf')

    def test_no_document_url_ever_names_supabase(self):
        """The whole failure was a template handing out a bucket address."""
        url = self.storage.url('link_requests/award.pdf')
        self.assertNotIn('supabase', url)
        self.assertNotIn('srms-media', url)
        self.assertNotIn('http', url)

    def test_a_signed_url_is_not_used_as_the_escape_hatch(self):
        """Signing would stop the error while keeping the hole.

        A signed URL answers whoever presents it, without asking who that is,
        so it is not a substitute for the check in api.media_views.
        """
        url = self.storage.url('documents/cog.pdf')
        for marker in ('X-Amz-Signature', 'X-Amz-Credential', '?'):
            self.assertNotIn(marker, url)

    def test_spaces_and_awkward_characters_survive_the_url(self):
        url = self.storage.url('documents/A Review of ARIMA vs ML.pdf')
        self.assertTrue(url.startswith('/media/documents/'))
        self.assertNotIn(' ', url)


@override_settings(**S3_SETTINGS)
class FileFieldUrlWithSupabaseTest(TestCase):
    """The same thing through a real model field, which is how templates get it."""

    def test_an_application_document_links_through_the_protected_view(self):
        from .models import Application, ApplicationDocument
        from .test_bootstrap import run as bootstrap_run  # settings + catalogue
        from django.contrib.auth import get_user_model
        from .models import Scholarship, StudentProfile

        User = get_user_model()
        bootstrap_run()

        user = User.objects.create_user(
            username='s@bipsu.edu.ph', email='s@bipsu.edu.ph',
            password='pw-for-test-only', role='student')
        profile = StudentProfile.objects.create(
            user=user, student_id='S-9001', course='BSIT', year_level=1)
        application = Application.objects.create(
            student=profile, scholarship=Scholarship.objects.get(type='Academic'),
            status='Pending', form_data={})

        doc = ApplicationDocument(application=application, name='COG')
        # Attach the name directly: saving would try to reach Supabase, and the
        # question here is only what URL the field reports.
        doc.file.name = 'documents/cog.pdf'

        self.assertEqual(doc.file.url, '/media/documents/cog.pdf')
