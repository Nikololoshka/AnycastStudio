from platforms2.core import AuthToken

from ..tiktok_answer import TikTokAnswer


class TokenAnswer(TikTokAnswer):
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    scope: str = ""

    def auth_token(self, requested_scopes: tuple[str, ...]) -> AuthToken:
        scopes = tuple(scope.strip() for scope in self.scope.split(",") if scope.strip())
        return AuthToken(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=self.expires_in,
            scopes=scopes or requested_scopes,
        )
