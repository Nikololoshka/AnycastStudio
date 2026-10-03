class InstagramEndpoints:
    GRAPH_VERSION = "v25.0"
    GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"
    RUPLOAD_ROOT = f"https://rupload.facebook.com/ig-api-upload/{GRAPH_VERSION}"
    AUTHORIZE = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
    TOKEN = f"{GRAPH_ROOT}/oauth/access_token"
    DEBUG_TOKEN = f"{GRAPH_ROOT}/debug_token"
    ME = f"{GRAPH_ROOT}/me"
    MY_PAGES = f"{GRAPH_ROOT}/me/accounts"

    @classmethod
    def node(cls, node_id: str) -> str:
        return f"{cls.GRAPH_ROOT}/{node_id}"

    @classmethod
    def permissions(cls, user_id: str) -> str:
        return f"{cls.GRAPH_ROOT}/{user_id}/permissions"

    @classmethod
    def media(cls, ig_user_id: str) -> str:
        return f"{cls.GRAPH_ROOT}/{ig_user_id}/media"

    @classmethod
    def media_publish(cls, ig_user_id: str) -> str:
        return f"{cls.GRAPH_ROOT}/{ig_user_id}/media_publish"

    @classmethod
    def rupload(cls, container_id: str) -> str:
        return f"{cls.RUPLOAD_ROOT}/{container_id}"
