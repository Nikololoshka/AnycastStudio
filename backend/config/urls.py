from django.urls import include, path

urlpatterns = [
    path("multiposter/", include("multiposter.urls")),
]

handler404 = "multiposter.views.common.not_found"
handler500 = "multiposter.views.common.server_error"
