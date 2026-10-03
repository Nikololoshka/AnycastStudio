from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PublishDraft:
    title: str
    description: str
    hashtags: tuple[str, ...] = ()
    settings: Mapping = field(default_factory=dict)

    def caption(self) -> str:
        tags = " ".join(f"#{tag}" for tag in self.hashtags)
        return "\n\n".join(part for part in (self.title.strip(), self.description.strip(), tags) if part)
