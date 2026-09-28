from ...core.http import PlatformModel, Present


class UserToken(PlatformModel):
    access_token: Present


class BusinessAccount(PlatformModel):
    id: str = ""
    username: str = ""
    name: str = ""
    profile_picture_url: str = ""


class Page(PlatformModel):
    id: str = ""
    access_token: str = ""
    instagram_business_account: BusinessAccount | None = None

    @property
    def is_linked(self) -> bool:
        return bool(self.access_token) and self.instagram_business_account is not None


class PageList(PlatformModel):
    data: list[Page] = []


class GranularScope(PlatformModel):
    target_ids: list[str] = []


class TokenInfo(PlatformModel):
    granular_scopes: list[GranularScope] = []
    user_id: str = ""


class DebugToken(PlatformModel):
    data: TokenInfo = TokenInfo()
