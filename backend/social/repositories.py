from platforms.core.auth.account import AccountRecord, AccountStatus
from platforms.core.ports import AccountRepository

from .models import SocialAccount


class DjangoAccountRepository(AccountRepository):
    def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]:
        rows = SocialAccount.objects.filter(user_id=owner_id).values_list("pk", "platform", "status")
        return {pk: AccountRecord(pk, platform, AccountStatus(status)) for pk, platform, status in rows}
