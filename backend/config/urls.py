from django.contrib import admin
from django.urls import path, re_path, include

from api import media_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('api.urls')),

    re_path(r'^media/(?P<path>.*)$', media_views.serve_media, name='media'),
]


handler400 = 'api.error_views.bad_request'
handler403 = 'api.error_views.permission_denied'
handler404 = 'api.error_views.page_not_found'
handler500 = 'api.error_views.server_error'
