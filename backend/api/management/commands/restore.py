"""Load a dump written by ``manage.py backup`` back into the database.

Refuses to run without ``--yes``, because the realistic moment for this is
an operator under pressure typing quickly at a production shell.
"""

import gzip
import os
import shutil
import tempfile

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Restore the database from a backup written by manage.py backup.'

    def add_arguments(self, parser):
        parser.add_argument('path', help='The .json.gz file to restore from.')
        parser.add_argument(
            '--yes', action='store_true',
            help='Required. Confirms that this database may be written to.',
        )
        parser.add_argument(
            '--flush', action='store_true',
            help='Empty every table first. Without it, rows whose primary key '
                 'is not in the backup are left in place.',
        )

    def handle(self, *args, **options):
        path = options['path']
        if not os.path.exists(path):
            raise CommandError(f'  restore: no such file: {path}')

        if not options['yes']:
            raise CommandError(
                f'  restore: this would overwrite {self._describe_target()} from '
                f'{path}.\n'
                '  Re-run with --yes once you are sure, and add --flush if the '
                'database should be emptied first.')

        if options['flush']:
            self.stdout.write('  restore: emptying every table')
            call_command('flush', '--no-input')

        temporary = self._unpacked(path)
        try:
            call_command('loaddata', temporary)
        except Exception as exc:
            raise CommandError(
                f'  restore: loaddata failed ({type(exc).__name__}: {exc}).\n'
                '  The database is part-written if --flush was passed. Restore '
                'again from a known-good file before letting anyone in.'
            ) from exc
        finally:
            os.unlink(temporary)

        self.stdout.write(self.style.SUCCESS(
            f'  restore: loaded {path} into {self._describe_target()}'))
        self.stdout.write(
            '  uploaded documents are not in this file. Check the matching '
            '.manifest.txt against the bucket before telling the office it is '
            'back.')

    def _describe_target(self):
        """The database this would write to, in words an operator recognises."""
        settings_dict = connection.settings_dict
        name = settings_dict.get('NAME')
        host = settings_dict.get('HOST')
        return f'{name} on {host}' if host else str(name)

    def _unpacked(self, path):
        """The backup as a plain .json file loaddata can read."""
        handle = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.json', delete=False)
        try:
            opener = gzip.open if path.endswith('.gz') else open
            with opener(path, 'rb') as source:
                shutil.copyfileobj(source, handle)
        finally:
            handle.close()
        return handle.name
