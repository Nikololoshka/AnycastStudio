from dataclasses import MISSING, asdict, dataclass, fields
from typing import Self


@dataclass
class ResumableState:
    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def of(cls, raw) -> Self | None:
        if not isinstance(raw, dict):
            return None
        values = {}
        for field in fields(cls):
            value = raw.get(field.name)
            if field.default is MISSING and not value:
                return None
            if value is None:
                continue
            try:
                values[field.name] = field.type(value)
            except (TypeError, ValueError):
                return None
        return cls(**values)
