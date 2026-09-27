from django.urls import path

from . import views

urlpatterns = [
    path("assets", views.media_assets, name="media-assets"),
    path("assets/<int:pk>", views.media_asset, name="media-asset"),
    path("uploads", views.media_upload_start, name="media-upload-start"),
    path("uploads/<uuid:upload_id>", views.media_upload_chunk, name="media-upload-chunk"),
    path("uploads/<uuid:upload_id>/status", views.media_upload_status, name="media-upload-status"),
    path("uploads/<uuid:upload_id>/complete", views.media_upload_complete, name="media-upload-complete"),
    path("uploads/<uuid:upload_id>/abort", views.media_upload_abort, name="media-upload-abort"),
]
