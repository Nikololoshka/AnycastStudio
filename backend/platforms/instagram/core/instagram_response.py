from platforms.core import PlatformFailure, PlatformResponse


class InstagramResponse(PlatformResponse):
    REFUSAL_LIMIT = 200
    TOKEN_REJECTED_CODES = (102, 190)
    MISCONFIGURED_CODES = (101, 191)
    PERMISSION_CODES = (10, *range(200, 300))
    THROTTLED_CODES = (4, 17, 32, 613)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and not self._graph_error()

    def failure(self) -> PlatformFailure:
        code = self._graph_error().get("code")
        if code in self.TOKEN_REJECTED_CODES:
            return PlatformFailure.TOKEN_REJECTED
        if code in self.MISCONFIGURED_CODES:
            return PlatformFailure.MISCONFIGURED
        if code in self.PERMISSION_CODES:
            return PlatformFailure.SCOPE_MISSING
        if code in self.THROTTLED_CODES or self.status == 429:
            return PlatformFailure.RATE_LIMITED
        if self.status == 408 or self.status >= 500:
            return PlatformFailure.NETWORK
        if self.status == 401:
            return PlatformFailure.TOKEN_REJECTED
        return PlatformFailure.REFUSED

    def refusal(self) -> str:
        error = self._graph_error()
        message = error.get("error_user_msg") or error.get("message")
        if message:
            return str(message)[: self.REFUSAL_LIMIT]
        return f"HTTP {self.status}"

    def _graph_error(self) -> dict:
        for key in ("error", "debug_info"):
            error = self.body.get(key)
            if isinstance(error, dict) and error:
                return error
        return {}
