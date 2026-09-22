"""Making an uploaded video visible, now or at a chosen moment.

YouTube schedules on its own side, so there is nothing for us to run later:
upload the video private, set status.publishAt, and YouTube publishes it. That
is why the scheduler the desktop client needed does not exist here.

The one rule that is easy to get wrong: publishAt is ignored unless
privacyStatus is private at the same time.
"""

from ..http import json_dict, request, with_retry
from .settings import YouTubeSettings

VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
LABEL = "YouTube"


def _status_body(video_id: str, settings_: YouTubeSettings, extra: dict) -> dict:
    return {
        "id": video_id,
        "status": {
            "license": settings_.license,
            "embeddable": settings_.embeddable,
            "publicStatsViewable": settings_.public_stats_viewable,
            "selfDeclaredMadeForKids": settings_.made_for_kids,
            "containsSyntheticMedia": settings_.contains_synthetic_media,
            **extra,
        },
    }


def _update(video_id: str, access_token: str, body: dict) -> dict:
    response = with_retry(
        lambda: request(
            "PUT",
            VIDEOS_ENDPOINT,
            label=LABEL,
            params={"part": "status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=body,
        ),
        label=LABEL,
    )
    return json_dict(response)


def publish(video_id: str, access_token: str, settings_: YouTubeSettings) -> str:
    """Set the final visibility and return the watch URL."""
    _update(video_id, access_token, _status_body(video_id, settings_, {"privacyStatus": settings_.privacy_status}))
    return watch_url(video_id)


def schedule(video_id: str, access_token: str, settings_: YouTubeSettings, publish_at: str) -> str:
    """Hand the timing to YouTube. The video stays private until that moment."""
    _update(
        video_id,
        access_token,
        _status_body(
            video_id, settings_, {"privacyStatus": "private", "publishAt": publish_at}
        ),
    )
    return watch_url(video_id)


def watch_url(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"
