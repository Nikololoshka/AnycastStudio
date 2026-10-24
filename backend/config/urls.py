from django.contrib import admin
from django.contrib.staticfiles.views import serve
from django.urls import include, path, re_path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/media/", include("media.urls")),
    path("api/", include("publishing.urls")),
    path("api/social/", include("social.urls")),
    re_path(r"^static/(?P<path>.*)$", serve, {"insecure": True}),
]

handler400 = "common.responses.error_views.bad_request"
handler403 = "common.responses.error_views.permission_denied"
handler404 = "common.responses.error_views.not_found"
handler500 = "common.responses.error_views.server_error"
