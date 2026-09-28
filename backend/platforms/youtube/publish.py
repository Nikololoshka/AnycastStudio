from .client import bearer, send
from .video_options import VideoOptions

VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"


def _status_body(video_id: str, options: VideoOptions, visibility: dict) -> dict:
    return {
        "id": video_id,
        "status": {
            "license": options.license,
            "embeddable": options.embeddable,
            "publicStatsViewable": options.public_stats_viewable,
            "selfDeclaredMadeForKids": options.made_for_kids,
            "containsSyntheticMedia": options.contains_synthetic_media,
            **visibility,
        },
    }


def _update(access_token: str, body: dict) -> None:
    send("PUT", VIDEOS_ENDPOINT, params={"part": "status"}, headers=bearer(access_token), json=body)


def publish(video_id: str, access_token: str, options: VideoOptions) -> str:
    _update(access_token, _status_body(video_id, options, {"privacyStatus": options.privacy_status}))
    return post_url(video_id)


def schedule(video_id: str, access_token: str, options: VideoOptions, publish_at: str) -> str:
    _update(access_token, _status_body(video_id, options, {"privacyStatus": "private", "publishAt": publish_at}))
    return post_url(video_id)


def post_url(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"
