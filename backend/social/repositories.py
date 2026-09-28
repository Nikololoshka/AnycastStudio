from platforms.core.auth.account import AccountRecord, AccountStatus
from platforms.core.errors import NotFound
from platforms.core.ports import AccountRepository

from .models import SocialAccount


class DjangoAccountRepository(AccountRepository):
    def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]:
        rows = SocialAccount.objects.filter(user_id=owner_id).values_list("pk", "platform", "status")
        return {pk: AccountRecord(pk, platform, AccountStatus(status)) for pk, platform, status in rows}

    def owned_account(self, owner_id: int, account_id: int, platform: str) -> AccountRecord:
        row = (
            SocialAccount.objects.filter(user_id=owner_id, pk=account_id, platform=platform)
            .exclude(status=SocialAccount.Status.REVOKED)
            .values_list("pk", "platform", "status")
            .first()
        )
        if row is None:
            raise NotFound()
        pk, platform, status = row
        return AccountRecord(pk, platform, AccountStatus(status))
