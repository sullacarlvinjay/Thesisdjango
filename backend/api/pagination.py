"""Pagination for the REST API.

Every list endpoint returned its whole queryset. That is fine against the few
dozen rows a demo holds and is not fine against a few years of intake: the
response grows without bound, and so does the memory the 512 MB container
needs to serialise it.

The page size is a default rather than a fixed rule — a caller that genuinely
wants more can ask, up to a ceiling, because a client forced to make forty
requests will simply make forty requests and the server gains nothing.

The response shape changes from a bare list to ``{count, next, previous,
results}``. That is a breaking change for any consumer reading the list
directly, which is why it is stated here: the rows now live under ``results``.
"""

from rest_framework.pagination import PageNumberPagination


class SRMSPagination(PageNumberPagination):
    """Page-number pagination with a caller-adjustable, capped page size.

    ``?page=2`` walks the pages; ``?page_size=200`` widens one. Anything above
    ``max_page_size`` is clamped rather than refused, so a caller asking for
    everything gets the most the server is willing to build instead of an
    error they have to handle.
    """

    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
