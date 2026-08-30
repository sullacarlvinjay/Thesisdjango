"""Limits on what may be uploaded.

The portal takes files from anyone who can reach the registration form, so the
FileFields need to say what they will accept rather than taking whatever
arrives. Two checks, both cheap:

* extension — an allowlist, not a denylist, because a denylist is only ever as
  current as the last thing someone thought of;
* size — a ceiling, so one upload cannot fill the disk or the storage quota.

These run on save. They are not a substitute for the access control in
:mod:`api.media_views`; they only decide what gets stored in the first place.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible

# Scans, photographs of certificates, and the occasional PDF export.
DOCUMENT_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'heic']

# Office imports: the scholar lists UniFAST and VPSEA roll over each term.
SPREADSHEET_EXTENSIONS = ['xlsx', 'xls', 'csv']


@deconstructible
class MaxFileSize:
    """Reject uploads past a ceiling, in megabytes.

    Deconstructible so migrations can serialise it; comparing by ``limit_mb``
    keeps makemigrations from emitting a fresh migration on every run.
    """

    def __init__(self, limit_mb=None):
        self.limit_mb = limit_mb

    @property
    def _limit(self):
        return self.limit_mb or getattr(settings, 'MAX_UPLOAD_SIZE_MB', 10)

    def __call__(self, value):
        limit_bytes = self._limit * 1024 * 1024
        if value.size > limit_bytes:
            raise ValidationError(
                f'That file is {value.size / 1024 / 1024:.1f} MB. '
                f'The limit is {self._limit} MB — please compress it and try again.'
            )

    def __eq__(self, other):
        return isinstance(other, MaxFileSize) and other.limit_mb == self.limit_mb

    def __hash__(self):
        return hash(('MaxFileSize', self.limit_mb))


validate_document = [
    FileExtensionValidator(allowed_extensions=DOCUMENT_EXTENSIONS),
    MaxFileSize(),
]

validate_spreadsheet = [
    FileExtensionValidator(allowed_extensions=SPREADSHEET_EXTENSIONS),
    MaxFileSize(),
]
