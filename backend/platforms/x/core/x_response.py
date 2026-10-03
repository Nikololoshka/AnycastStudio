from platforms.core import PlatformFailure, PlatformResponse


class XResponse(PlatformResponse):
    REFUSAL_LIMIT = 200
    PROBLEM_PREFIX = "https://api.x.com/2/problems/"
    INVALID_TOKEN_MARK = "was invalid"
    OAUTH_FAILURES = {
        "invalid_grant": PlatformFailure.GRANT_REVOKED,
        "invalid_client": PlatformFailure.MISCONFIGURED,
        "unauthorized_client": PlatformFailure.MISCONFIGURED,
        "invalid_scope": PlatformFailure.MISCONFIGURED,
        "invalid_request": PlatformFailure.MISCONFIGURED,
    }
    PROBLEM_FAILURES = {
        "usage-capped": PlatformFailure.RATE_LIMITED,
        "client-forbidden": PlatformFailure.MISCONFIGURED,
    }

    def failure(self) -> PlatformFailure:
        error = self.body.get("error")
        if isinstance(error, str):
            if self.INVALID_TOKEN_MARK in str(self.body.get("error_description") or ""):
                return PlatformFailure.GRANT_REVOKED
            return self.OAUTH_FAILURES.get(error, PlatformFailure.REFUSED)
        if self._problem_kind() in self.PROBLEM_FAILURES:
            return self.PROBLEM_FAILURES[self._problem_kind()]
        if self.status == 408 or self.status >= 500:
            return PlatformFailure.NETWORK
        if self.status == 429:
            return PlatformFailure.RATE_LIMITED
        if self.status == 401:
            return PlatformFailure.TOKEN_REJECTED
        return PlatformFailure.REFUSED

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
