from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "display_name", "is_active", "is_staff", "date_joined"]
    search_fields = ["email", "display_name"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Profile", {"fields": ["display_name", "locale", "timezone", "theme"]}),
        (
            "Limits",
            {
                "fields": [
                    "max_storage_bytes",
                    "max_media_asset_bytes",
                    "max_concurrent_uploads",
                    "max_publications_per_day",
                ]
            },
        ),
        ("Permissions", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "password1", "password2"]}),
    ]
