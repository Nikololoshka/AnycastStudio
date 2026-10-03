from platforms2.core import AuthToken

from ..x_answer import XAnswer


class TokenAnswer(XAnswer):
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    scope: str = ""

    def auth_token(self, requested_scopes: tuple[str, ...]) -> AuthToken:
        return AuthToken(
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            expires_in=self.expires_in,
            scopes=tuple(self.scope.split()) or requested_scopes,
        )
