"""The chunked upload protocol.

Mirrors the resumable protocol the platforms themselves use: the client asks
where to continue from, sends one piece at a time, and the server is the only
authority on how far it got. A dropped connection costs one chunk, not the
whole file.
"""

import logging

from pydantic import BaseModel, Field

from common.guards import rate_limit, require_auth, require_delete, require_get, require_post
from common.responses import api_response
from common.schema import validate

from .. import services
from ..models import UploadSession
from ..serializers import asset_json, session_json

logger = logging.getLogger(__name__)


class StartUploadSchema(BaseModel):
    filename: str = Field(min_length=1, max_length=260)
    sizeBytes: int = Field(gt=0)
    mimeType: str = Field(max_length=100)
    sha256: str = Field(default="", max_length=64)


class CompleteUploadSchema(BaseModel):
    durationSeconds: float | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)


def _session_of(request, upload_id) -> UploadSession | None:
    # Filtered by user, so somebody else's upload is not found rather than forbidden.
    return UploadSession.objects.filter(user=request.user, upload_id=upload_id).first()


@require_post
@require_auth
@rate_limit("uploads")
@validate(StartUploadSchema)
def start(request, data):
    try:
        session = services.start(
            request.user, data.filename, data.mimeType, data.sizeBytes, data.sha256
        )
    except services.TooLarge as error:
        return api_response("payload_too_large", limit=error.limit)
    except services.TooManyUploads as error:
        return api_response("conflict", message="too_many_uploads", limit=error.limit)
    except services.QuotaExceeded as error:
        return api_response("quota_exceeded", used=error.used, limit=error.limit)

    return api_response("ok", **session_json(session))


@require_get
@require_auth
def status(request, upload_id):
    session = _session_of(request, upload_id)
    if session is None:
        return api_response("not_found")
    if session.status != UploadSession.Status.OPEN:
        return api_response("expired")
    if session.is_stale:
        services.abort(session)
        return api_response("expired")

    return api_response("ok", **session_json(session))


@require_auth
def chunk(request, upload_id):
    """PATCH one piece at the offset the client believes the server is at."""
    if request.method != "PATCH":
        return api_response("method_not_allowed", headers={"Allow": "PATCH"})

    session = _session_of(request, upload_id)
    if session is None:
        return api_response("not_found")
    if session.status != UploadSession.Status.OPEN or session.is_stale:
        return api_response("expired")

    try:
        offset = int(request.headers.get("Upload-Offset", ""))
    except ValueError:
        return api_response("invalid", errors=[{"field": "Upload-Offset", "message": "required"}])

    # The client and the server disagree about how much arrived, which happens
    # whenever a connection drops mid-chunk. Tell it where we actually are.
    if offset != session.received_bytes:
        return api_response("conflict", offset=session.received_bytes)

    new_offset = services.receive_chunk(session, request)

    if new_offset > session.declared_size:
        services.abort(session)
        return api_response("invalid", errors=[{"field": "body", "message": "more bytes than declared"}])

    return api_response("ok", offset=new_offset)


@require_post
@require_auth
@validate(CompleteUploadSchema)
def complete(request, data, upload_id):
    session = _session_of(request, upload_id)
    if session is None:
        return api_response("not_found")
    if session.status != UploadSession.Status.OPEN:
        return api_response("expired")

    if session.received_bytes != session.declared_size:
        return api_response(
            "conflict", offset=session.received_bytes, expected=session.declared_size
        )

    try:
        asset = services.complete(session, data.durationSeconds, data.width, data.height)
    except ValueError as error:
        services.abort(session)
        return api_response("invalid", errors=[{"field": "sha256", "message": str(error)}])

    return api_response("ok", asset=asset_json(asset))


@require_delete
@require_auth
def abort(request, upload_id):
    session = _session_of(request, upload_id)
    if session is None:
        return api_response("not_found")

    if session.status == UploadSession.Status.OPEN:
        services.abort(session)
    return api_response("ok")
