"""The deploy-time proof that uploads will work.

Worth testing carefully because it runs under `set -o errexit`: if it raises
when it should not, it stops a deploy that would have been fine, and if it
stays quiet when the credentials are wrong the failure lands on a student
instead.

Nothing here touches a network. The storage backend is substituted, which is
also the only honest way to test the failure branches — a real bucket cannot be
asked to produce SignatureDoesNotMatch on demand.
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .management.commands import check_storage


def run(**kwargs):
    out, err = StringIO(), StringIO()
    call_command('check_storage', stdout=out, stderr=err, **kwargs)
    return out.getvalue() + err.getvalue()


class LocalStorageTest(TestCase):

    @override_settings(USE_SUPABASE_STORAGE=False)
    def test_it_does_nothing_when_uploads_are_local(self):
        """A laptop and the test suite have no remote store, and must not need one."""
        output = run()
        self.assertIn('nothing to check', output)


@override_settings(USE_SUPABASE_STORAGE=True)
class RemoteStorageTest(TestCase):

    def test_a_working_bucket_reports_success_and_leaves_nothing_behind(self):
        saved = {}

        def fake_save(name, content):
            saved['name'] = name
            saved['data'] = content.read()
            return name

        deleted = []
        with mock.patch.object(check_storage.default_storage, 'save', fake_save), \
             mock.patch.object(check_storage.default_storage, 'open',
                               lambda n, m='rb': mock.MagicMock(
                                   __enter__=lambda s: mock.Mock(
                                       read=lambda: saved['data']),
                                   __exit__=lambda *a: False)), \
             mock.patch.object(check_storage.default_storage, 'delete', deleted.append):
            output = run()

        self.assertIn('uploads will work', output)
        self.assertEqual(deleted, [saved['name']], 'the probe must be removed')
        self.assertTrue(saved['name'].startswith(check_storage.PROBE_PREFIX))

    def test_a_bad_secret_stops_the_deploy_and_names_the_variable(self):
        boom = Exception('An error occurred (SignatureDoesNotMatch) when calling PutObject')
        with mock.patch.object(check_storage.default_storage, 'save',
                               side_effect=boom):
            with self.assertRaises(CommandError) as caught:
                run()
        message = str(caught.exception)
        self.assertIn('SUPABASE_S3_SECRET_ACCESS_KEY', message)
        self.assertIn('FAILED', message)

    def test_a_missing_bucket_names_the_bucket_variable(self):
        boom = Exception('An error occurred (NoSuchBucket) when calling PutObject')
        with mock.patch.object(check_storage.default_storage, 'save',
                               side_effect=boom):
            with self.assertRaises(CommandError) as caught:
                run()
        self.assertIn('SUPABASE_STORAGE_BUCKET', str(caught.exception))

    def test_a_wrong_region_is_recognised(self):
        boom = Exception('An error occurred (AuthorizationHeaderMalformed): region')
        with mock.patch.object(check_storage.default_storage, 'save',
                               side_effect=boom):
            with self.assertRaises(CommandError) as caught:
                run()
        self.assertIn('SUPABASE_S3_REGION', str(caught.exception))

    def test_an_unrecognised_error_still_stops_the_deploy(self):
        with mock.patch.object(check_storage.default_storage, 'save',
                               side_effect=Exception('something new')):
            with self.assertRaises(CommandError) as caught:
                run()
        self.assertIn('SUPABASE_S3_ENDPOINT', str(caught.exception))

    def test_a_bucket_that_returns_the_wrong_bytes_is_a_failure(self):
        """Reachable is not the same as working."""
        with mock.patch.object(check_storage.default_storage, 'save',
                               lambda n, c: n), \
             mock.patch.object(check_storage.default_storage, 'open',
                               lambda n, m='rb': mock.MagicMock(
                                   __enter__=lambda s: mock.Mock(
                                       read=lambda: b'not what was written'),
                                   __exit__=lambda *a: False)), \
             mock.patch.object(check_storage.default_storage, 'delete', lambda n: None):
            with self.assertRaises(CommandError) as caught:
                run()
        self.assertIn('not returning what was stored', str(caught.exception))

    def test_warn_only_reports_the_problem_without_failing_the_build(self):
        boom = Exception('An error occurred (SignatureDoesNotMatch) when calling PutObject')
        with mock.patch.object(check_storage.default_storage, 'save',
                               side_effect=boom):
            output = run(warn_only=True)
        self.assertIn('uploads will fail', output)

    def test_a_probe_that_cannot_be_deleted_does_not_fail_the_deploy(self):
        """A few stray bytes are not worth blocking a release over."""
        with mock.patch.object(check_storage.default_storage, 'save',
                               lambda n, c: n), \
             mock.patch.object(check_storage.default_storage, 'open',
                               lambda n, m='rb': mock.MagicMock(
                                   __enter__=lambda s: mock.Mock(
                                       read=lambda: b'srms storage check'),
                                   __exit__=lambda *a: False)), \
             mock.patch.object(check_storage.default_storage, 'delete',
                               side_effect=Exception('denied')):
            output = run()
        self.assertIn('could not remove the probe', output)
        self.assertIn('uploads will work', output)
