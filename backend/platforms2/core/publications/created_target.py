from dataclasses import dataclass

from ..platform_type import PlatformType


@dataclass(frozen=True)
class CreatedTarget:
    id: int
    platform: PlatformType
