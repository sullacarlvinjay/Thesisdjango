"""Write a restorable copy of the database and a manifest of the uploads.

Portable on purpose: the deployed database is Postgres and the local one is
SQLite, and ``pg_dump`` is not in the deploy container. ``dumpdata`` speaks
both, so one command and one file format cover every environment the system
actually runs in.

The uploads themselves are not copied — they live in a Supabase bucket that
is backed up as a bucket. What is written here is a manifest naming every
file the database expects to find, so a restore can say which documents are
missing instead of discovering it one scholar at a time.
"""

import gzip
import io
import os
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

EXCLUDED = (
    'contenttypes',
    'auth.Permission',
    'sessions.Session',
    'admin.LogEntry',
    'authtoken.Token',
)

def _file_fields():
    """Every stored-file column in the application, found rather than listed.

    A hand-kept list goes stale the first time someone adds a document field
    and forgets this file, and a manifest that quietly omits a whole class of
    uploads is worse than none at all.
    """
    from django.apps import apps
    from django.db.models import FileField

    found = []
    for model in apps.get_app_config('api').get_models():
        for field in model._meta.get_fields():
            if isinstance(field, FileField):
                found.append((model, field.name))
    return found


class Command(BaseCommand):
    help = ('Write a timestamped, restorable dump of the database plus a '
            'manifest of every uploaded file it refers to.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', default='backups',
            help='Directory to write into. Created if missing. Default: backups/',
        )
        parser.add_argument(
            '--label', default='',
            help='Extra word in the filename, e.g. "pre-migration".',
        )
        parser.add_argument(
            '--no-manifest', action='store_true',
            help='Skip the upload manifest, which needs one query per file field.',
        )

    def handle(self, *args, **options):
        folder = options['output']
        os.makedirs(folder, exist_ok=True)

        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        label = f"-{options['label']}" if options['label'] else ''
        data_path = os.path.join(folder, f'srms-{stamp}{label}.json.gz')

        self._write_data(data_path)
        self.stdout.write(self.style.SUCCESS(
            f'  backup: {data_path} ({os.path.getsize(data_path):,} bytes)'))

        if not options['no_manifest']:
            manifest_path = os.path.join(
                folder, f'srms-{stamp}{label}.manifest.txt')
            counted = self._write_manifest(manifest_path)
            self.stdout.write(self.style.SUCCESS(
                f'  backup: {manifest_path} ({counted} uploaded file(s))'))

        self.stdout.write(
            '  restore it with: python manage.py restore '
            f'{data_path} --yes')

    def _write_data(self, path):
        """Dump every application table into one gzipped JSON file."""
        buffer = io.StringIO()
        try:
            call_command(
                'dumpdata',
                *(f'--exclude={name}' for name in EXCLUDED),
                natural_foreign=True,
                indent=None,
                stdout=buffer,
            )
        except Exception as exc:
            raise CommandError(
                f'  backup: dumpdata failed ({type(exc).__name__}). Nothing was '
                'written.') from exc

        with gzip.open(path, 'wt', encoding='utf-8') as handle:
            handle.write(buffer.getvalue())

    def _write_manifest(self, path):
        """List every stored file the database expects to find."""
        from django.core.files.storage import default_storage

        lines = []
        for model, field in _file_fields():
            dotted = f'{model._meta.app_label}.{model.__name__}.{field}'
            names = (model.objects.exclude(**{field: ''})
                     .values_list(field, flat=True))
            for name in names:
                if not name:
                    continue
                size = self._size_of(default_storage, name)
                lines.append(f'{dotted}\t{name}\t{size}')

        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('# model.field\tstored name\tbytes (-1 = missing)\n')
            handle.write('\n'.join(sorted(lines)))
            handle.write('\n')
        return len(lines)

    def _size_of(self, storage, name):
        """A stored file's size, or -1 where the store cannot produce it."""
        try:
            return storage.size(name)
        except Exception:
            return -1
