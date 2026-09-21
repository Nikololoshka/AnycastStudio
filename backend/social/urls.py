from django.urls import path

from . import views

urlpatterns = [
    # Facebook
    path("auth_facebook/start", views.start, {"provider": "facebook"}, name="facebook-start"),
    path("auth_facebook/callback", views.callback, {"provider": "facebook"}, name="facebook-callback"),
    path("auth_facebook/poll", views.poll, {"provider": "facebook"}, name="facebook-poll"),
]
