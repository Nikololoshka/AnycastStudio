from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AwaitingConfirmation:
    confirmation_state: Mapping = field(default_factory=dict)
