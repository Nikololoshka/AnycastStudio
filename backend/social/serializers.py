def account_json(account) -> dict:
    """What the SPA is allowed to know about a connected account.

    No token field appears here, and none ever should: the browser has no use
    for one, and anything in an API response ends up in somebody's log.
    """
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
