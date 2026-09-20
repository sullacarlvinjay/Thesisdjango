"""Upload validators.

An extension allow-list and a size ceiling read from ``SystemSettings``, so the
office can change the limit without a redeploy.

These run during ``full_clean()``, which a plain ``save()`` does not call. A
view that assigns an upload straight to a field and saves gets no validation at
all, and must call the checks itself.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible

DOCUMENT_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'heic']

SPREADSHEET_EXTENSIONS = ['xlsx', 'xls', 'csv']


@deconstructible
class MaxFileSize:
    """Reject an upload larger than the configured ceiling.

    Deconstructible and comparing by limit so Django does not write a new
    migration every time it is used.

    The limit is read at validation time, not at import: ``None`` defers to
    ``MAX_UPLOAD_SIZE_MB``, so the office can change it without a redeploy.
    """
    def __init__(self, limit_mb=None):
        self.limit_mb = limit_mb

    @property
    def _limit(self):
        """The ceiling in megabytes, read fresh from settings."""
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
