import logging

from django.core.cache import cache

from common.access import require_auth, require_get
from common.rate_limit import rate_limit
from common.responses import api_response
from platforms import tiktok
from platforms.core.errors import NeedsFreshToken, PlatformError, ProviderError

from .. import services
from ..models import SocialAccount

logger = logging.getLogger(__name__)

CACHE_SECONDS = 300


def _cache_key(account: SocialAccount) -> str:
    return f"tiktok-creator-info:{account.pk}"


def _query(account: SocialAccount) -> tiktok.CreatorInfo:
    try:
        return tiktok.creator_info(services.get_valid_access_token(account))
    except NeedsFreshToken:
        return tiktok.creator_info(services.refresh_access_token(account))


def _platform_unavailable(account: SocialAccount, reason: str):
    logger.info("Creator info for account %s failed: %s", account.pk, reason)
    return api_response("server_error", message="platform_unavailable")


@require_get
@require_auth
@rate_limit("creator_info")
def social_creator_info(request, pk: int):
    account = (
        SocialAccount.objects.filter(user=request.user, pk=pk, platform="tiktok")
        .exclude(status=SocialAccount.Status.REVOKED)
        .first()
    )
    if account is None:
        return api_response("not_found")
    if account.status == SocialAccount.Status.NEEDS_REAUTH:
        return api_response("conflict", message="account_needs_reauth", platform=account.platform)

    info = cache.get(_cache_key(account))
    if info is None:
        try:
            info = _query(account).as_json()
        except ProviderError as error:
            if error.transient:
                return _platform_unavailable(account, error.message)
            return api_response("conflict", message="account_needs_reauth", platform=account.platform)
        except NeedsFreshToken:
            return api_response("conflict", message="account_needs_reauth", platform=account.platform)
        except PlatformError as failure:
            return _platform_unavailable(account, failure.message)
        cache.set(_cache_key(account), info, CACHE_SECONDS)

    return api_response("ok", creatorInfo=info)
