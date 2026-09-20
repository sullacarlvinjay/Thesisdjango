"""Storage backends.

Uploads go to a private bucket whose URLs point back at this application rather
than at the bucket, so every request for a scholar document passes the access
check in ``media_views``. Static files are minified during ``collectstatic``,
which keeps the build pure Python and the digest in each filename honest.
"""

import logging
import os

from django.conf import settings
from django.utils.encoding import filepath_to_uri
from storages.backends.s3 import S3Storage
from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ProtectedS3Storage(S3Storage):
    """S3 storage whose URLs point back at this application.

    The bucket is private and the default backend would hand out a signed
    URL straight to it — a link that works for anyone who gets hold of it,
    for as long as the signature lasts. Routing through ``MEDIA_URL``
    instead means every request for a scholar's document passes
    ``api/media_views.py``, which checks who is asking.
    """
    def url(self, name, parameters=None, expire=None, http_method=None):
        """A URL served by this application, not by the bucket."""
        return f'{settings.MEDIA_URL}{filepath_to_uri(name)}'


class MinifiedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Static storage that minifies CSS and JS on the way through.

    Minifying during ``collectstatic`` keeps the build pure Python — no
    Node on the server — and means the hash in each filename is taken from
    the minified bytes, so the manifest and the served file always agree.
    """
    def post_process(self, paths, dry_run=False, **options):
        """Minify first, then let the parent hash and compress.

        Files that were shrunk are re-read from disk rather than from the
        original source, so the digest matches what is actually served.
        """
        if not dry_run:
            rewired = {}
            for name, source in paths.items():
                rewired[name] = (self, name) if self._minify(name) else source
            paths = rewired
        yield from super().post_process(paths, dry_run=dry_run, **options)

    def _minify(self, name):
        """Shrink one file in place, reporting whether it changed.

        Refuses in every case where shrinking would be wrong or pointless: a
        file that is not CSS or JS, one already named ``.min``, one that
        cannot be read as text, and one whose minified form is no smaller.
        A minifier that throws is logged and the file ships unchanged — a
        deploy should not fail over whitespace.
        """
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
