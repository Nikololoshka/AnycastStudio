from dataclasses import dataclass

from platforms.core import PlatformType


@dataclass(frozen=True)
class CreatedTarget:
    id: int
    platform: PlatformType
