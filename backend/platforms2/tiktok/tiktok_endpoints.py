class TikTokEndpoints:
    API_ROOT = "https://open.tiktokapis.com/v2"
    AUTHORIZE = "https://www.tiktok.com/v2/auth/authorize/"
    TOKEN = f"{API_ROOT}/oauth/token/"
    REVOKE = f"{API_ROOT}/oauth/revoke/"
    USER_INFO = f"{API_ROOT}/user/info/"
