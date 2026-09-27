from ..models import UploadSession, MediaAsset


def session_json(session: UploadSession) -> dict:
    return {
        "uploadId": str(session.upload_id),
        "offset": session.received_bytes,
        "sizeBytes": session.declared_size,
        "chunkSize": session.chunk_size,
        "filename": session.filename,
    }


def asset_json(asset: MediaAsset) -> dict:
    return {
        "id": asset.pk,
        "filename": asset.filename,
        "mimeType": asset.mime_type,
        "sizeBytes": asset.size_bytes,
        "durationSeconds": asset.duration_seconds,
        "width": asset.width,
        "height": asset.height,
        "status": asset.status,
        "createdAt": asset.created_at.isoformat(),
    }
