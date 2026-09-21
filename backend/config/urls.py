from django.urls import include, path

urlpatterns = [
    path("api/social/", include("social.urls")),
]

handler404 = "social.views.common.not_found"
handler500 = "social.views.common.server_error"
