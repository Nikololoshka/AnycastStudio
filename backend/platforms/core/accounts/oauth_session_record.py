from dataclasses import dataclass, field

from ..platform_type import PlatformType


@dataclass(frozen=True)
class OAuthSessionRecord:
    id: int
    owner_id: int
    platform: PlatformType
    code_verifier: str = field(default="", repr=False)
