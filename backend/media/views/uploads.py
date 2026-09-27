from common.access import require_auth, require_delete, require_get, require_patch, require_post
from common.rate_limit import rate_limit
from common.request_body import validate
from common.responses import api_response

from .. import services
from ..models import UploadSession
from .schemas import CompleteUploadSchema, StartUploadSchema
from .serializers import asset_json, session_json


def _session_of(request, upload_id) -> UploadSession | None:
    return UploadSession.objects.filter(user=request.user, upload_id=upload_id).first()


def _upload_offset(request) -> int | None:
    try:
        return int(request.headers.get("Upload-Offset", ""))
    except ValueError:
        return None


@require_post
@require_auth
@rate_limit("uploads")
@validate(StartUploadSchema)
def media_upload_start(request, data: StartUploadSchema):
    try:
        session = services.start(request.user, data.filename, data.mimeType, data.sizeBytes, data.sha256)
    except services.TooLarge as error:
        return api_response("payload_too_large", limit=error.limit)
    except services.TooManyUploads as error:
        return api_response("conflict", message="too_many_uploads", limit=error.limit)
    except services.QuotaExceeded as error:
        return api_response("quota_exceeded", used=error.used, limit=error.limit)

    return api_response("ok", **session_json(session))


@require_get
@require_auth
def media_upload_status(request, upload_id):
    session = _session_of(request, upload_id)
    if session is None:
        return api_response("not_found")
    if session.status != UploadSession.Status.OPEN:
        return api_response("expired")
    if session.is_stale:
        services.abort(session)
        return api_response("expired")

    return api_response("ok", **session_json(session))


@require_patch
@require_auth
def media_upload_chunk(request, upload_id):
    session = _session_of(request, upload_id)
    if session is None:
        return api_response("not_found")
    if session.status != UploadSession.Status.OPEN or session.is_stale:
        return api_response("expired")

    offset = _upload_offset(request)
    if offset is None:
        return api_response("invalid", errors=[{"field": "Upload-Offset", "message": "required"}])

    try:
        new_offset = services.receive_chunk(session, offset, request)
    except services.OffsetConflict as conflict:
        return api_response("conflict", offset=conflict.offset)
    except services.MoreBytesThanDeclared:
        return api_response("invalid", errors=[{"field": "body", "message": "more bytes than declared"}])

    return api_response("ok", offset=new_offset)


@require_post
@require_auth
@validate(CompleteUploadSchema)
def media_upload_complete(request, data: CompleteUploadSchema, upload_id):
    session = _session_of(request, upload_id)
    if session is None:
        return api_response("not_found")
    if session.status != UploadSession.Status.OPEN:
        return api_response("expired")

    if session.received_bytes != session.declared_size:
        return api_response("conflict", offset=session.received_bytes, expected=session.declared_size)

    try:
        asset = services.complete(session, data.durationSeconds, data.width, data.height)
    except services.AlreadyFinished:
        return api_response("expired")
    except services.ChecksumMismatch:
        return api_response("invalid", errors=[{"field": "sha256", "message": "checksum_mismatch"}])

    return api_response("ok", asset=asset_json(asset))


@require_delete
@require_auth
def media_upload_abort(request, upload_id):
    session = _session_of(request, upload_id)
    if session is None:
        return api_response("not_found")

    if session.status == UploadSession.Status.OPEN:
        services.abort(session)
    return api_response("ok")
