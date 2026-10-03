from dataclasses import dataclass

from platforms2.core import AuthFailure


@dataclass(frozen=True)
class TikTokResponse:
    REFUSAL_LIMIT = 200
    OK_CODE = "ok"
    CODE_FAILURES = {
        "access_token_invalid": AuthFailure.TOKEN_REJECTED,
        "scope_not_authorized": AuthFailure.SCOPE_MISSING,
        "rate_limit_exceeded": AuthFailure.RATE_LIMITED,
        "invalid_grant": AuthFailure.GRANT_REVOKED,
        "invalid_client": AuthFailure.MISCONFIGURED,
        "unauthorized_client": AuthFailure.MISCONFIGURED,
        "invalid_scope": AuthFailure.MISCONFIGURED,
        "invalid_request": AuthFailure.MISCONFIGURED,
    }

    status: int
    body: dict

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and not self.error_code

    @property
    def error_code(self) -> str:
        error = self.body.get("error")
        if isinstance(error, dict):
            code = str(error.get("code") or "")
            return "" if code == self.OK_CODE else code
        return str(error or "")

    def failure(self) -> AuthFailure:
        if self.error_code in self.CODE_FAILURES:
            return self.CODE_FAILURES[self.error_code]
        if self.status == 408 or self.status >= 500:
            return AuthFailure.NETWORK
        if self.status == 429:
            return AuthFailure.RATE_LIMITED
        if self.status == 401:
            return AuthFailure.TOKEN_REJECTED
        return AuthFailure.REFUSED

    def refusal(self) -> str:
        error = self.body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or self.error_code)[: self.REFUSAL_LIMIT]
        if error:
            return str(self.body.get("error_description") or error)[: self.REFUSAL_LIMIT]
        return f"HTTP {self.status}"
