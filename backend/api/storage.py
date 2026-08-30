"""Where uploaded files live, and how a browser is allowed to reach them.

Switching the storage backend to Supabase quietly changed something the rest of
the app depends on. Templates link documents with ``{{ doc.file.url }}``, and
that call returns whatever the backend thinks the file's address is:

    FileSystemStorage  ->  /media/documents/cog.pdf      (api.media_views)
    S3Storage          ->  https://<project>/storage/v1/s3/srms-media/...

The second address goes straight to Supabase and never passes through the view
that decides who may read a document. Against a private bucket the browser gets
``AccessDenied: Missing signature``; against a public one it would get the
document, which is worse — every permission check in api.media_views would be
bypassed by a link the template itself produced.

Signing the URLs instead (``querystring_auth``) fixes the error but not the
problem: a signed URL is a bearer token for that file, valid for anyone who has
it, and it still answers without ever asking who is holding it.

So the address stays ``/media/…`` whatever the backend. Django keeps storing
bytes in Supabase; browsers keep talking to api.media_views, which checks the
requester and then reads those bytes server-side.
"""

from django.conf import settings
from django.utils.encoding import filepath_to_uri
from storages.backends.s3 import S3Storage


class ProtectedS3Storage(S3Storage):
    """Supabase Storage for the bytes, our own URL for the address."""

    def url(self, name, parameters=None, expire=None, http_method=None):
        # Deliberately not calling super(): its return value is the bucket URL,
        # which is exactly what must not reach a template.
        return f'{settings.MEDIA_URL}{filepath_to_uri(name)}'
