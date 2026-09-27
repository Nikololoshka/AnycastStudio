from django.contrib import admin

from .models import OAuthSession, SocialAccount


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ["platform", "display_name", "user", "status", "connected_at"]
    list_filter = ["platform", "status"]
    search_fields = ["display_name", "external_id", "user__email"]
    exclude = ["access_token", "refresh_token"]
    readonly_fields = ["key_version", "token_expires_at", "last_refresh_at", "connected_at"]


@admin.register(OAuthSession)
class OAuthSessionAdmin(admin.ModelAdmin):
    list_display = ["platform", "user", "status", "created_at"]
    list_filter = ["platform", "status"]
    exclude = ["code_verifier", "state"]
