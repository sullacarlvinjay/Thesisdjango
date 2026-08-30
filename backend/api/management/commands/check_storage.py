"""Prove the file store actually works, at deploy time.

settings.py checks only that the SUPABASE_S3_* variables are *set*. A wrong
region, a mistyped endpoint or a bad secret all start the site perfectly and
fail much later, the first time somebody uploads a document — by which point
the error belongs to a student filling in a form, and the deploy that caused
it is days behind.

So the deploy does one round trip: write a small object, read it back, delete
it. Anything wrong with the credentials, the endpoint or the bucket surfaces
here, in the build log, with the cause named.

Does nothing when uploads are on the local filesystem — a laptop and the test
suite have no remote store to check, and this must not become a reason the
tests need network access.
"""

import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

# Written and removed on every deploy. The prefix is not one api.media_views
# recognises, so even if a probe is ever left behind it is unreadable through
# the site rather than quietly public.
PROBE_PREFIX = 'healthcheck/'

# What the common failures actually mean, in the words of the dashboard the
# reader has to go back to.
HINTS = [
    ('SignatureDoesNotMatch',
     'SUPABASE_S3_SECRET_ACCESS_KEY is wrong. Regenerate the pair under '
     'Storage > S3 connection; the secret is shown only once.'),
    ('InvalidAccessKeyId',
     'SUPABASE_S3_ACCESS_KEY_ID does not exist. It is the S3 access key, not '
     'the project API key.'),
    ('NoSuchBucket',
     'No bucket by that name. Check SUPABASE_STORAGE_BUCKET, and that the '
     'bucket has actually been created under Storage.'),
    ('AccessDenied',
     'The key exists but may not write to this bucket.'),
    ('EndpointConnectionError',
     'SUPABASE_S3_ENDPOINT could not be reached. It should look like '
     'https://<ref>.supabase.co/storage/v1/s3'),
    ('Could not connect',
     'SUPABASE_S3_ENDPOINT could not be reached.'),
    ('IllegalLocationConstraint',
     'SUPABASE_S3_REGION does not match the project region.'),
    ('AuthorizationHeaderMalformed',
     'SUPABASE_S3_REGION does not match the project region.'),
]


class Command(BaseCommand):
    help = 'Write, read back and delete one object, to prove uploads will work.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--warn-only', action='store_true',
            help='Report a broken store without failing the build. For getting '
                 'a deploy out while the storage credentials are still being '
                 'sorted out — uploads will not work until they are.',
        )

    def handle(self, *args, **options):
        if not getattr(settings, 'USE_SUPABASE_STORAGE', False):
            self.stdout.write('  storage: local filesystem, nothing to check')
            return

        name = f'{PROBE_PREFIX}deploy-{uuid.uuid4().hex}.txt'
        payload = b'srms storage check'
        written = None

        try:
            written = default_storage.save(name, ContentFile(payload))
            with default_storage.open(written, 'rb') as handle:
                read_back = handle.read()
            if read_back != payload:
                raise CommandError(
                    f'  storage: wrote {len(payload)} bytes to {written} but read '
                    f'back {len(read_back)}. The bucket is reachable but not '
                    'returning what was stored.'
                )
        except CommandError:
            raise
        except Exception as exc:
            message = self._explain(exc)
            if options['warn_only']:
                self.stderr.write(self.style.WARNING(message))
                self.stderr.write(self.style.WARNING(
                    '  continuing because --warn-only was passed: uploads will fail.'))
                return
            raise CommandError(message) from None
        finally:
            if written:
                try:
                    default_storage.delete(written)
                except Exception:
                    # Not worth failing a deploy over: the probe is a few bytes
                    # in a prefix nothing serves.
                    self.stderr.write(self.style.WARNING(
                        f'  storage: could not remove the probe {written}'))

        self.stdout.write(self.style.SUCCESS(
            f'  storage: wrote, read and deleted {name} — uploads will work'))

    def _explain(self, exc):
        text = f'{type(exc).__name__}: {exc}'
        lines = [f'  storage: FAILED — {text}']
        for marker, hint in HINTS:
            if marker.lower() in text.lower():
                lines.append(f'  likely cause: {hint}')
                break
        else:
            lines.append('  Check SUPABASE_S3_ENDPOINT, SUPABASE_S3_REGION, the '
                         'access key pair and SUPABASE_STORAGE_BUCKET.')
        lines.append('  Uploaded documents would fail for students, so the deploy '
                     'is stopped here. Pass --warn-only to deploy anyway.')
        return '\n'.join(lines)
