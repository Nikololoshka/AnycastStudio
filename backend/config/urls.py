from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Reachable only over an SSH tunnel: no public server config routes it.
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/social/", include("social.urls")),
]

handler404 = "common.responses.not_found"
handler500 = "common.responses.server_error"
