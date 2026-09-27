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
        "quota": {
            "maxStorageBytes": user.max_storage_bytes,
            "maxMediaAssetBytes": user.max_media_asset_bytes,
            "maxConcurrentUploads": user.max_concurrent_uploads,
            "maxPublicationsPerDay": user.max_publications_per_day,
        },
    }
