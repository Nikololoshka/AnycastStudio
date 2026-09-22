"""Creating publications and watching what happens to them."""

import logging

from django.utils.dateparse import parse_datetime
from pydantic import BaseModel, Field

from common.guards import rate_limit, require_auth, require_get, require_post
from common.responses import api_response
from common.schema import validate
from media.models import MediaAsset
from platforms.base import ProviderError
from social.models import SocialAccount

from .. import services
from ..models import Publication, PublicationTarget
from ..serializers import publication_json

logger = logging.getLogger(__name__)


class TargetSchema(BaseModel):
    platform: str = Field(max_length=32)
    socialAccountId: int
    settings: dict = Field(default_factory=dict)


class CreatePublicationSchema(BaseModel):
    mediaAssetId: int
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10_000)
    hashtags: list[str] = Field(default_factory=list, max_length=60)
    publishAt: str | None = None
    targets: list[TargetSchema] = Field(min_length=1, max_length=4)


@require_post
@require_auth
@rate_limit("publications")
@validate(CreatePublicationSchema)
def create(request, data):
    asset = MediaAsset.objects.filter(
        user=request.user, pk=data.mediaAssetId, status=MediaAsset.Status.READY
    ).first()
    if asset is None:
        return api_response("not_found", message="media_asset")

    publish_at = parse_datetime(data.publishAt) if data.publishAt else None
    if data.publishAt and publish_at is None:
        return api_response("invalid", errors=[{"field": "publishAt", "message": "not a datetime"}])

    accounts = {account.pk: account for account in SocialAccount.objects.filter(user=request.user)}
    for target in data.targets:
        account = accounts.get(target.socialAccountId)
        if account is None or account.platform != target.platform:
            return api_response("not_found", message="social_account")
        if account.status != SocialAccount.Status.ACTIVE:
            return api_response("conflict", message="account_needs_reauth", platform=account.platform)

    try:
        publication = services.create_publication(
            user=request.user,
            asset=asset,
            title=data.title,
            description=data.description,
            hashtags=list(data.hashtags),
            publish_at=publish_at,
            targets=[target.model_dump() for target in data.targets],
        )
    except services.DailyLimitReached as error:
        return api_response("quota_exceeded", message="daily_limit", limit=error.limit)
    except ProviderError as error:
        return api_response("conflict", message=error.message)

    services.dispatch(publication)
    return api_response("ok", publication=publication_json(publication))


def _publications_of(user):
    return Publication.objects.filter(user=user).prefetch_related("targets").select_related("asset")


@require_get
@require_auth
def publications(request):
    rows = _publications_of(request.user).order_by("-created_at")[:100]
    return api_response("ok", publications=[publication_json(row) for row in rows])


@require_get
@require_auth
def publication(request, pk: int):
    row = _publications_of(request.user).filter(pk=pk).first()
    if row is None:
        return api_response("not_found")
    return api_response("ok", publication=publication_json(row))


def _target_of(request, pk: int) -> PublicationTarget | None:
    # Reached only through its owner's publication, so another tenant's target
    # is not found rather than forbidden.
    return PublicationTarget.objects.filter(publication__user=request.user, pk=pk).first()


@require_post
@require_auth
def cancel_target(request, pk: int):
    target = _target_of(request, pk)
    if target is None:
        return api_response("not_found")
    if not services.request_cancel(target):
        return api_response("conflict", message="not_running")

    target.refresh_from_db()
    return api_response("ok", publication=publication_json(target.publication))


@require_post
@require_auth
def retry_target(request, pk: int):
    target = _target_of(request, pk)
    if target is None:
        return api_response("not_found")
    if not services.retry(target):
        return api_response("conflict", message="not_retryable")

    target.refresh_from_db()
    return api_response("ok", publication=publication_json(target.publication))
