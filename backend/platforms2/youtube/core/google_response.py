from platforms2.core import PlatformFailure, PlatformResponse


class GoogleResponse(PlatformResponse):
    REFUSAL_LIMIT = 200
    OAUTH_FAILURES = {
        "invalid_grant": PlatformFailure.GRANT_REVOKED,
        "invalid_client": PlatformFailure.MISCONFIGURED,
        "unauthorized_client": PlatformFailure.MISCONFIGURED,
        "redirect_uri_mismatch": PlatformFailure.MISCONFIGURED,
        "invalid_scope": PlatformFailure.MISCONFIGURED,
        "invalid_request": PlatformFailure.MISCONFIGURED,
    }
    API_REASON_FAILURES = {
        "quotaExceeded": PlatformFailure.RATE_LIMITED,
        "rateLimitExceeded": PlatformFailure.RATE_LIMITED,
        "userRateLimitExceeded": PlatformFailure.RATE_LIMITED,
        "dailyLimitExceeded": PlatformFailure.RATE_LIMITED,
        "uploadLimitExceeded": PlatformFailure.RATE_LIMITED,
        "insufficientPermissions": PlatformFailure.SCOPE_MISSING,
        "ACCESS_TOKEN_SCOPE_INSUFFICIENT": PlatformFailure.SCOPE_MISSING,
        "invalidTitle": PlatformFailure.INVALID,
        "invalidDescription": PlatformFailure.INVALID,
        "invalidTags": PlatformFailure.INVALID,
        "invalidCategoryId": PlatformFailure.INVALID,
        "invalidPublishAt": PlatformFailure.INVALID,
        "invalidVideoMetadata": PlatformFailure.INVALID,
        "mediaBodyRequired": PlatformFailure.FILE_REJECTED,
    }

    def failure(self) -> PlatformFailure:
        if self.status == 408 or self.status >= 500:
            return PlatformFailure.NETWORK
        if self.status == 429:
            return PlatformFailure.RATE_LIMITED

        error = self.body.get("error")
        if isinstance(error, str):
            return self.OAUTH_FAILURES.get(error, PlatformFailure.REFUSED)
        for reason in self._api_reasons():
            if reason in self.API_REASON_FAILURES:
                return self.API_REASON_FAILURES[reason]
        if self.status == 401:
            return PlatformFailure.TOKEN_REJECTED
        return PlatformFailure.REFUSED

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
