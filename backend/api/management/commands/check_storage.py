import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

PROBE_PREFIX = 'healthcheck/'

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
