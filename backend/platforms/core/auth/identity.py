from dataclasses import dataclass, field


@dataclass(frozen=True)
class Identity:
    external_id: str
    display_name: str
    avatar_url: str = ""
    extra: dict = field(default_factory=dict)
