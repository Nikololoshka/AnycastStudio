from django.contrib import admin

from .models import MediaAsset, UploadSession


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ["filename", "user", "size_bytes", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["filename", "user__email"]


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    list_display = ["filename", "user", "received_bytes", "declared_size", "status", "last_activity_at"]
    list_filter = ["status"]
