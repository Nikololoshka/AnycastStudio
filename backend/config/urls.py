from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/media/", include("media.urls")),
    path("api/", include("publishing.urls")),
    path("api/social/", include("social.urls")),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()

handler400 = "common.responses.error_views.bad_request"
handler403 = "common.responses.error_views.permission_denied"
handler404 = "common.responses.error_views.not_found"
handler500 = "common.responses.error_views.server_error"
