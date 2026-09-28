from ..client import YouTubeClient
from ..options import YouTubeOptions

VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
POST_URL = "https://youtu.be/{video_id}"


class YouTubeVisibility:
    def __init__(self, client: YouTubeClient):
        self._client = client

    def publish(self, video_id: str, access_token: str, options: YouTubeOptions) -> str:
        self._update(access_token, video_id, options, {"privacyStatus": options.privacy_status})
        return self.post_url(video_id)

    def schedule(self, video_id: str, access_token: str, options: YouTubeOptions, publish_at: str) -> str:
        self._update(access_token, video_id, options, {"privacyStatus": "private", "publishAt": publish_at})
        return self.post_url(video_id)

    @staticmethod
    def post_url(video_id: str) -> str:
        return POST_URL.format(video_id=video_id)

    def _update(self, access_token: str, video_id: str, options: YouTubeOptions, visibility: dict) -> None:
        body = {"id": video_id, "status": {**options.status_fields(), **visibility}}
        headers = self._client.bearer(access_token)
        self._client.send("PUT", VIDEOS_ENDPOINT, params={"part": "status"}, headers=headers, json=body)
