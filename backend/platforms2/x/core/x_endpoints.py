class XEndpoints:
    API_ROOT = "https://api.x.com/2"
    AUTHORIZE = "https://x.com/i/oauth2/authorize"
    TOKEN = f"{API_ROOT}/oauth2/token"
    REVOKE = f"{API_ROOT}/oauth2/revoke"
    ME = f"{API_ROOT}/users/me"
    MEDIA_UPLOAD = f"{API_ROOT}/media/upload"
    MEDIA_INITIALIZE = f"{API_ROOT}/media/upload/initialize"
    TWEETS = f"{API_ROOT}/tweets"
    POST = "https://x.com/i/web/status/{post_id}"

    @classmethod
    def media_append(cls, media_id: str) -> str:
        return f"{cls.MEDIA_UPLOAD}/{media_id}/append"

    @classmethod
    def media_finalize(cls, media_id: str) -> str:
        return f"{cls.MEDIA_UPLOAD}/{media_id}/finalize"
