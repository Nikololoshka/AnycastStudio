from django.urls import path

from . import views

urlpatterns = [
    path("assets", views.assets, name="media-assets"),
    path("assets/<int:pk>", views.asset, name="media-asset"),
    path("uploads", views.start, name="media-upload-start"),
    path("uploads/<uuid:upload_id>", views.chunk, name="media-upload-chunk"),
    path("uploads/<uuid:upload_id>/status", views.status, name="media-upload-status"),
    path("uploads/<uuid:upload_id>/complete", views.complete, name="media-upload-complete"),
    path("uploads/<uuid:upload_id>/abort", views.abort, name="media-upload-abort"),
]
