from django.urls import path

from . import views

urlpatterns = [
    path("publications", views.publishing_list_publications, name="publications"),
    path("publications/create", views.publishing_create_publication, name="publication-create"),
    path("publications/<int:pk>", views.publishing_get_publication, name="publication"),
    path("targets/<int:pk>/cancel", views.publishing_cancel_target, name="target-cancel"),
    path("targets/<int:pk>/retry", views.publishing_retry_target, name="target-retry"),
    path("drafts", views.publishing_list_drafts, name="drafts"),
    path("drafts/create", views.publishing_create_draft, name="draft-create"),
    path("drafts/<int:pk>", views.publishing_get_draft, name="draft"),
    path("drafts/<int:pk>/update", views.publishing_update_draft, name="draft-update"),
    path("drafts/<int:pk>/delete", views.publishing_delete_draft, name="draft-delete"),
    path("platforms", views.publishing_list_platform_capabilities, name="platforms"),
]
