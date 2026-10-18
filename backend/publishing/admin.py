from django.contrib import admin

from .models import Draft, Publication, PublicationTarget


class TargetInline(admin.TabularInline):
    model = PublicationTarget
    extra = 0
    readonly_fields = ["platform", "status", "progress", "published_url", "error"]


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "publish_at", "created_at", "hidden_at"]
    search_fields = ["title", "user__email"]
    inlines = [TargetInline]


@admin.register(PublicationTarget)
class PublicationTargetAdmin(admin.ModelAdmin):
    list_display = ["publication", "platform", "status", "progress", "attempt_count"]
    list_filter = ["platform", "status"]


@admin.register(Draft)
class DraftAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "asset", "updated_at"]
    search_fields = ["title", "user__email"]
