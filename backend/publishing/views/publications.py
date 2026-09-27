from django.utils import timezone

from common.access import require_auth, require_get, require_post
from common.rate_limit import rate_limit
from common.request_body import validate
from common.responses import api_response
from media.models import MediaAsset
from social.models import SocialAccount

from .. import services
from ..models import Publication, PublicationTarget
from .schemas import CreatePublicationSchema
from .serializers import publication_json


def _publications_of(user):
    return Publication.objects.filter(user=user).prefetch_related("targets").select_related("asset")


def _target_of(request, pk: int) -> PublicationTarget | None:
    return PublicationTarget.objects.filter(publication__user=request.user, pk=pk).first()


def _account_refusal(request, data: CreatePublicationSchema):
    accounts = {account.pk: account for account in SocialAccount.objects.filter(user=request.user)}
    for target in data.targets:
        account = accounts.get(target.socialAccountId)
        if account is None or account.platform != target.platform:
            return api_response("not_found", message="social_account")
        if account.status != SocialAccount.Status.ACTIVE:
            return api_response("conflict", message="account_needs_reauth", platform=account.platform)
    return None


@require_post
@require_auth
@rate_limit("publications")
@validate(CreatePublicationSchema)
def publishing_create(request, data: CreatePublicationSchema):
    asset = MediaAsset.objects.filter(
        user=request.user, pk=data.mediaAssetId, status=MediaAsset.Status.READY
    ).first()
    if asset is None:
        return api_response("not_found", message="media_asset")

    if data.publishAt and data.publishAt <= timezone.now():
        return api_response("invalid", errors=[{"field": "publishAt", "message": "must be in the future"}])

    refusal = _account_refusal(request, data)
    if refusal:
        return refusal

    try:
        publication = services.create_publication(
            user=request.user,
            asset=asset,
            title=data.title,
            description=data.description,
            hashtags=list(data.hashtags),
            publish_at=data.publishAt,
            targets=[target.model_dump() for target in data.targets],
        )
    except services.DailyLimitReached as error:
        return api_response("quota_exceeded", message="daily_limit", limit=error.limit)

    services.dispatch(publication)
    return api_response("ok", publication=publication_json(publication))


@require_get
@require_auth
def publishing_publications(request):
    rows = _publications_of(request.user).order_by("-created_at")[:100]
    return api_response("ok", publications=[publication_json(row) for row in rows])


@require_get
@require_auth
def publishing_publication(request, pk: int):
    row = _publications_of(request.user).filter(pk=pk).first()
    if row is None:
        return api_response("not_found")
    return api_response("ok", publication=publication_json(row))


@require_post
@require_auth
def publishing_cancel_target(request, pk: int):
    target = _target_of(request, pk)
    if target is None:
        return api_response("not_found")
    if not services.request_cancel(target):
        return api_response("conflict", message="not_running")

    target.refresh_from_db()
    return api_response("ok", publication=publication_json(target.publication))


@require_post
@require_auth
def publishing_retry_target(request, pk: int):
    target = _target_of(request, pk)
    if target is None:
        return api_response("not_found")
    if not services.retry(target):
        return api_response("conflict", message="not_retryable")

    target.refresh_from_db()
    return api_response("ok", publication=publication_json(target.publication))
