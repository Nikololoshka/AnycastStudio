class XEndpoints:
    API_ROOT = "https://api.x.com/2"
    AUTHORIZE = "https://x.com/i/oauth2/authorize"
    TOKEN = f"{API_ROOT}/oauth2/token"
    REVOKE = f"{API_ROOT}/oauth2/revoke"
    ME = f"{API_ROOT}/users/me"
