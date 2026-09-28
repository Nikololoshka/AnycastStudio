from platforms.core.ports import AccessTokens

from . import services
from .models import SocialAccount


class DjangoAccessTokens(AccessTokens):
    def valid(self, account_id: int) -> str:
        return services.get_valid_access_token(SocialAccount.objects.get(pk=account_id))

    def refresh(self, account_id: int) -> str:
        return services.refresh_access_token(SocialAccount.objects.get(pk=account_id))
