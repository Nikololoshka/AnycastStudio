from ..models import SocialAccount


def account_json(account: SocialAccount) -> dict:
    return {
        "id": account.pk,
        "platform": account.platform,
        "externalId": account.external_id,
        "displayName": account.display_name,
        "avatarUrl": account.avatar_url,
        "status": account.status,
        "connectedAt": account.connected_at.isoformat(),
        "needsReauth": account.status == account.Status.NEEDS_REAUTH,
    }
