from dataclasses import dataclass

from ..platform_type import PlatformType
from .account_status import AccountStatus


@dataclass(frozen=True)
class AccountRecord:
    id: int
    platform: PlatformType
    status: AccountStatus
