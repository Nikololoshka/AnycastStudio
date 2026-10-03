from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors
