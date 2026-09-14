from django.test import TestCase, override_settings

from .storage import ProtectedS3Storage

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
        url = self.storage.url('link_requests/award.pdf')
        self.assertNotIn('supabase', url)
        self.assertNotIn('srms-media', url)
        self.assertNotIn('http', url)

    def test_a_signed_url_is_not_used_as_the_escape_hatch(self):
        url = self.storage.url('documents/cog.pdf')
        for marker in ('X-Amz-Signature', 'X-Amz-Credential', '?'):
            self.assertNotIn(marker, url)

    def test_spaces_and_awkward_characters_survive_the_url(self):
        url = self.storage.url('documents/A Review of ARIMA vs ML.pdf')
        self.assertTrue(url.startswith('/media/documents/'))
        self.assertNotIn(' ', url)


@override_settings(**S3_SETTINGS)
class FileFieldUrlWithSupabaseTest(TestCase):
    def test_an_application_document_links_through_the_protected_view(self):
        from .models import Application, ApplicationDocument
        from .test_bootstrap import run as bootstrap_run
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
        doc.file.name = 'documents/cog.pdf'

        self.assertEqual(doc.file.url, '/media/documents/cog.pdf')
