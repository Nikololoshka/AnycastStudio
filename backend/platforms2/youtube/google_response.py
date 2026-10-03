from dataclasses import dataclass


@dataclass(frozen=True)
class GoogleResponse:
    REFUSAL_LIMIT = 200

    status: int
    body: dict

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def transient(self) -> bool:
        return self.status in (408, 429) or self.status >= 500

    def refusal(self) -> str:
        error = self.body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("status") or "")[: self.REFUSAL_LIMIT]
        if isinstance(error, str):
            return str(self.body.get("error_description") or error)[: self.REFUSAL_LIMIT]
        return f"HTTP {self.status}"
