from ..errors import FailureType, PlatformError

MESSAGE_LIMIT = 500


class FailureClassifier:
    def classify(self, response, label: str) -> PlatformError | None:
        status = response.status_code

        if 200 <= status < 300 or status == 308:
            return None

        message = self.message_of(response, label)

        if status == 401:
            return PlatformError(FailureType.AUTHENTICATION, message or "The connection expired")
        if status == 403:
            return PlatformError(FailureType.AUTHORIZATION, message or "The platform refused")
        if status == 429:
            return PlatformError(FailureType.RATE_LIMIT, message or "Too many requests", retryable=True)
        if status in (400, 404, 409, 422):
            return PlatformError(FailureType.VALIDATION, message or "The platform rejected the request")
        if status >= 500 or status == 408:
            return PlatformError(FailureType.PLATFORM, message or "The platform is unavailable", retryable=True)

        return PlatformError(FailureType.PLATFORM, message)

    def message_of(self, response, label: str) -> str:
        body = self._json_dict(response)
        error = body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("status") or "")[:MESSAGE_LIMIT]
        if isinstance(error, str):
            return str(body.get("error_description") or error)[:MESSAGE_LIMIT]
        return f"{label} answered HTTP {response.status_code}"

    @staticmethod
    def _json_dict(response) -> dict:
        try:
            data = response.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
