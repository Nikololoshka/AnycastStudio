from dataclasses import dataclass

from platforms2.core import AuthFailure


@dataclass(frozen=True)
class XResponse:
    REFUSAL_LIMIT = 200
    PROBLEM_PREFIX = "https://api.x.com/2/problems/"
    INVALID_TOKEN_MARK = "was invalid"
    OAUTH_FAILURES = {
        "invalid_grant": AuthFailure.GRANT_REVOKED,
        "invalid_client": AuthFailure.MISCONFIGURED,
        "unauthorized_client": AuthFailure.MISCONFIGURED,
        "invalid_scope": AuthFailure.MISCONFIGURED,
        "invalid_request": AuthFailure.MISCONFIGURED,
    }
    PROBLEM_FAILURES = {
        "usage-capped": AuthFailure.RATE_LIMITED,
        "client-forbidden": AuthFailure.MISCONFIGURED,
    }

    status: int
    body: dict

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def failure(self) -> AuthFailure:
        error = self.body.get("error")
        if isinstance(error, str):
            if self.INVALID_TOKEN_MARK in str(self.body.get("error_description") or ""):
                return AuthFailure.GRANT_REVOKED
            return self.OAUTH_FAILURES.get(error, AuthFailure.REFUSED)
        if self._problem_kind() in self.PROBLEM_FAILURES:
            return self.PROBLEM_FAILURES[self._problem_kind()]
        if self.status == 408 or self.status >= 500:
            return AuthFailure.NETWORK
        if self.status == 429:
            return AuthFailure.RATE_LIMITED
        if self.status == 401:
            return AuthFailure.TOKEN_REJECTED
        return AuthFailure.REFUSED

    def refusal(self) -> str:
        if isinstance(self.body.get("error"), str):
            return str(self.body.get("error_description") or self.body["error"])[: self.REFUSAL_LIMIT]
        problem = self._problem()
        text = problem.get("detail") or problem.get("title") or problem.get("message")
        if text:
            return str(text)[: self.REFUSAL_LIMIT]
        return f"HTTP {self.status}"

    def _problem_kind(self) -> str:
        return str(self._problem().get("type") or "").removeprefix(self.PROBLEM_PREFIX)

    def _problem(self) -> dict:
        if any(self.body.get(key) for key in ("type", "detail", "title")):
            return self.body
        errors = self.body.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict) and not self.body.get("data"):
            return errors[0]
        return {}
