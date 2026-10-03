from collections.abc import Mapping
from dataclasses import dataclass, field

from ..platform_type import PlatformType


@dataclass(frozen=True)
class NewTarget:
    platform: PlatformType
    account_id: int
    settings: Mapping = field(default_factory=dict)
