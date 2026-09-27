from django.urls import path

from . import views

urlpatterns = [
    path("publications", views.publishing_publications, name="publications"),
    path("publications/create", views.publishing_create, name="publication-create"),
    path("publications/<int:pk>", views.publishing_publication, name="publication"),
    path("targets/<int:pk>/cancel", views.publishing_cancel_target, name="target-cancel"),
    path("targets/<int:pk>/retry", views.publishing_retry_target, name="target-retry"),
    path("platforms", views.publishing_platforms, name="platforms"),
]
