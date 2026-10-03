from platforms2.core import AuthFailure, PlatformResponse


class GoogleResponse(PlatformResponse):
    REFUSAL_LIMIT = 200
    OAUTH_FAILURES = {
        "invalid_grant": AuthFailure.GRANT_REVOKED,
        "invalid_client": AuthFailure.MISCONFIGURED,
        "unauthorized_client": AuthFailure.MISCONFIGURED,
        "redirect_uri_mismatch": AuthFailure.MISCONFIGURED,
        "invalid_scope": AuthFailure.MISCONFIGURED,
        "invalid_request": AuthFailure.MISCONFIGURED,
    }
    API_REASON_FAILURES = {
        "quotaExceeded": AuthFailure.RATE_LIMITED,
        "rateLimitExceeded": AuthFailure.RATE_LIMITED,
        "userRateLimitExceeded": AuthFailure.RATE_LIMITED,
        "dailyLimitExceeded": AuthFailure.RATE_LIMITED,
        "insufficientPermissions": AuthFailure.SCOPE_MISSING,
        "ACCESS_TOKEN_SCOPE_INSUFFICIENT": AuthFailure.SCOPE_MISSING,
    }

    def failure(self) -> AuthFailure:
        if self.status == 408 or self.status >= 500:
            return AuthFailure.NETWORK
        if self.status == 429:
            return AuthFailure.RATE_LIMITED

        error = self.body.get("error")
        if isinstance(error, str):
            return self.OAUTH_FAILURES.get(error, AuthFailure.REFUSED)
        for reason in self._api_reasons():
            if reason in self.API_REASON_FAILURES:
                return self.API_REASON_FAILURES[reason]
        if self.status == 401:
            return AuthFailure.TOKEN_REJECTED
        return AuthFailure.REFUSED

    def refusal(self) -> str:
        error = self.body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("status") or "")[: self.REFUSAL_LIMIT]
        if isinstance(error, str):
            return str(self.body.get("error_description") or error)[: self.REFUSAL_LIMIT]
        return f"HTTP {self.status}"

    def _api_reasons(self) -> list[str]:
        error = self.body.get("error")
        if not isinstance(error, dict):
            return []
        entries = [*(error.get("errors") or []), *(error.get("details") or [])]
        return [str(entry.get("reason")) for entry in entries if isinstance(entry, dict) and entry.get("reason")]
