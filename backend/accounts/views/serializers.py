from platforms import PlatformCatalog
from platforms.core import PlatformType


def user_json(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "displayName": user.display_name,
        "name": user.name,
        "isStaff": user.is_staff,
        "locale": user.locale,
        "timezone": user.timezone,
        "theme": user.theme,
        "mediaRetentionDays": user.media_retention_days,
        "defaultPlatforms": [*PlatformType] if user.default_platforms is None else user.default_platforms,
        "platformDefaults": {
            platform: PlatformCatalog.normalized_settings(platform, user.platform_defaults.get(platform, {}))
            for platform in PlatformType
        },
        "quota": {
            "maxStorageBytes": user.max_storage_bytes,
            "maxMediaAssetBytes": user.max_media_asset_bytes,
            "maxConcurrentUploads": user.max_concurrent_uploads,
            "maxPublicationsPerDay": user.max_publications_per_day,
        },
    }
