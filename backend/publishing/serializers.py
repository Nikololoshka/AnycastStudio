def target_json(target) -> dict:
    return {
        "id": target.pk,
        "platform": target.platform,
        "socialAccountId": target.social_account_id,
        "settings": target.settings,
        "status": target.status,
        "progress": target.progress,
        "uploadedBytes": target.uploaded_bytes,
        "totalBytes": target.total_bytes,
        "publishedUrl": target.published_url,
        "error": target.error,
        "attemptCount": target.attempt_count,
        "isActive": target.is_active,
        "startedAt": target.started_at.isoformat() if target.started_at else None,
        "finishedAt": target.finished_at.isoformat() if target.finished_at else None,
    }


def publication_json(publication) -> dict:
    targets = list(publication.targets.all())
    return {
        "id": publication.pk,
        "title": publication.title,
        "description": publication.description,
        "hashtags": publication.hashtags,
        "publishAt": publication.publish_at.isoformat() if publication.publish_at else None,
        "createdAt": publication.created_at.isoformat(),
        "mediaAssetId": publication.asset_id,
        "filename": publication.asset.filename,
        "targets": [target_json(target) for target in targets],
        # One flag so the browser knows whether to keep polling.
        "isActive": any(target.is_active for target in targets),
    }
