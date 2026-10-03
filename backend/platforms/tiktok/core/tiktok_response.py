from platforms.core import PlatformFailure, PlatformResponse


class TikTokResponse(PlatformResponse):
    REFUSAL_LIMIT = 200
    OK_CODE = "ok"
    CODE_FAILURES = {
        "access_token_invalid": PlatformFailure.TOKEN_REJECTED,
        "scope_not_authorized": PlatformFailure.SCOPE_MISSING,
        "rate_limit_exceeded": PlatformFailure.RATE_LIMITED,
        "invalid_grant": PlatformFailure.GRANT_REVOKED,
        "invalid_client": PlatformFailure.MISCONFIGURED,
        "unauthorized_client": PlatformFailure.MISCONFIGURED,
        "invalid_scope": PlatformFailure.MISCONFIGURED,
        "invalid_request": PlatformFailure.MISCONFIGURED,
        "privacy_level_option_mismatch": PlatformFailure.INVALID,
        "unaudited_client_can_only_post_to_private_accounts": PlatformFailure.INVALID,
        "spam_risk_too_many_posts": PlatformFailure.RATE_LIMITED,
        "spam_risk_too_many_pending_share": PlatformFailure.RATE_LIMITED,
    }

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

    def failure(self) -> PlatformFailure:
        if self.error_code in self.CODE_FAILURES:
            return self.CODE_FAILURES[self.error_code]
        if self.status == 408 or self.status >= 500:
            return PlatformFailure.NETWORK
        if self.status == 429:
            return PlatformFailure.RATE_LIMITED
        if self.status == 401:
            return PlatformFailure.TOKEN_REJECTED
        return PlatformFailure.REFUSED

    def refusal(self) -> str:
        error = self.body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or self.error_code)[: self.REFUSAL_LIMIT]
        if error:
            return str(self.body.get("error_description") or error)[: self.REFUSAL_LIMIT]
        return f"HTTP {self.status}"
