from django.conf import settings
from django.utils.encoding import filepath_to_uri
from storages.backends.s3 import S3Storage


class ProtectedS3Storage(S3Storage):
    def url(self, name, parameters=None, expire=None, http_method=None):
        return f'{settings.MEDIA_URL}{filepath_to_uri(name)}'
