from django.contrib import admin
from django.urls import path, re_path, include

from api import media_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('api.urls')),

    # Uploads are student documents, so they go through a view that checks who
    # is asking. This replaces django.conf.urls.static.static(), which served
    # every file to anyone and returned nothing at all once DEBUG was off.
    re_path(r'^media/(?P<path>.*)$', media_views.serve_media, name='media'),
]


# Django's stock error pages are written for whoever wrote the code, not for
# whoever hit the error. api/error_views.py says what happened in plain words
# and puts a way out on the page. Only reached with DEBUG off — with it on,
# Django keeps showing its own traceback pages.
handler400 = 'api.error_views.bad_request'
handler403 = 'api.error_views.permission_denied'
handler404 = 'api.error_views.page_not_found'
handler500 = 'api.error_views.server_error'
