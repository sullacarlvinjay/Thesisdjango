import logging
import os

from django.conf import settings
from django.utils.encoding import filepath_to_uri
from storages.backends.s3 import S3Storage
from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ProtectedS3Storage(S3Storage):
    def url(self, name, parameters=None, expire=None, http_method=None):
        return f'{settings.MEDIA_URL}{filepath_to_uri(name)}'


class MinifiedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    def post_process(self, paths, dry_run=False, **options):
        if not dry_run:
            rewired = {}
            for name, source in paths.items():
                rewired[name] = (self, name) if self._minify(name) else source
            paths = rewired
        yield from super().post_process(paths, dry_run=dry_run, **options)

    def _minify(self, name):
        root, ext = os.path.splitext(name)
        ext = ext.lower()
        if ext == '.css':
            import rcssmin as minifier
            shrink = minifier.cssmin
        elif ext == '.js':
            import rjsmin as minifier
            shrink = minifier.jsmin
        else:
            return False
        if root.endswith('.min'):
            return False
        path = self.path(name)
        try:
            with open(path, encoding='utf-8') as handle:
                source = handle.read()
        except (OSError, UnicodeDecodeError):
            return False
        try:
            shrunk = shrink(source)
        except Exception:
            logger.warning('could not minify %s, shipping it unchanged', name)
            return False
        if not shrunk or len(shrunk) >= len(source):
            return False
        with open(path, 'w', encoding='utf-8', newline='') as handle:
            handle.write(shrunk)
        return True
