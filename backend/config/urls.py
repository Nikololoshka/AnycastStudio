from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

urlpatterns = [
    # Reachable only over an SSH tunnel: no public server config routes it.
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/media/", include("media.urls")),
    path("api/", include("publishing.urls")),
    path("api/social/", include("social.urls")),
]

if settings.DEBUG:
    # The admin's own CSS. staticfiles only serves it automatically under
    # runserver, and this project runs uvicorn. Nothing else needs static
    # files: the SPA is served by Vite.
    urlpatterns += staticfiles_urlpatterns()

handler404 = "common.responses.not_found"
handler500 = "common.responses.server_error"
