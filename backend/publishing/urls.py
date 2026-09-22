from django.urls import path

from . import views

urlpatterns = [
    path("publications", views.publications, name="publications"),
    path("publications/create", views.create, name="publication-create"),
    path("publications/<int:pk>", views.publication, name="publication"),
    path("targets/<int:pk>/cancel", views.cancel_target, name="target-cancel"),
    path("targets/<int:pk>/retry", views.retry_target, name="target-retry"),
    path("platforms", views.platforms, name="platforms"),
]
