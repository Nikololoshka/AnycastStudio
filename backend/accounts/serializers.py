"""Shapes the SPA receives. Kept by hand so the wire format is visible in one place."""


def user_json(user) -> dict:
    quota = user.quota
    return {
        "id": user.id,
        "email": user.email,
        "displayName": user.display_name,
        "name": user.name,
        "isStaff": user.is_staff,
        "locale": user.locale,
        "timezone": user.timezone,
        "theme": user.theme,
        "quota": {
            "maxStorageBytes": quota.max_storage_bytes,
            "maxMediaAssetBytes": quota.max_media_asset_bytes,
            "maxConcurrentUploads": quota.max_concurrent_uploads,
            "maxPublicationsPerDay": quota.max_publications_per_day,
        },
    }
