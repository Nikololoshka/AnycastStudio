from ...core import InstagramAnswer


class GranularScope(InstagramAnswer):
    target_ids: list[str] = []


class TokenInfo(InstagramAnswer):
    granular_scopes: list[GranularScope] = []
    user_id: str = ""


class DebugToken(InstagramAnswer):
    data: TokenInfo = TokenInfo()

    def granted_asset_ids(self) -> list[str]:
        asset_ids: list[str] = []
        for scope in self.data.granular_scopes:
            for target in scope.target_ids:
                if target not in asset_ids:
                    asset_ids.append(target)
        return asset_ids
