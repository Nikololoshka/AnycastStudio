from abc import ABC, abstractmethod

from .auth_profile import AuthProfile
from .auth_request import AuthRequest
from .auth_token import AuthToken


class AuthorizationInteractor(ABC):

    @abstractmethod
    def create_auth_request(self, state: str) -> AuthRequest: ...

    @abstractmethod
    async def create_auth_token(self, code: str, code_verifier: str) -> AuthToken: ...

    @abstractmethod
    async def refresh_auth_token(self, refresh_token: str) -> AuthToken: ...

    @abstractmethod
    async def fetch_auth_profile(self, access_token: str) -> AuthProfile: ...

    @abstractmethod
    async def revoke_auth_token(self, token: str) -> None: ...
