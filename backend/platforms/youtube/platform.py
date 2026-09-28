from ..core.config import PlatformConfig
from ..core.platform import Platform, PlatformFactory
from ..core.ports import Clock
from .auth import YouTubeProvider
from .client import LABEL, YouTubeClient
from .options import CAPABILITIES, YouTubeValidator
from .publish import YouTubePublisher, YouTubeVisibility
from .upload import ResumableProtocol, YouTubeUploader


class YouTubeFactory(PlatformFactory):
    def build(self, config: PlatformConfig, clock: Clock) -> Platform:
        client = YouTubeClient(config.http)
        uploader = YouTubeUploader(ResumableProtocol(client), config.upload)
        return Platform(
            name=YouTubeProvider.name,
            label=LABEL,
            capabilities=CAPABILITIES,
            provider=YouTubeProvider.create(config),
            publisher=YouTubePublisher(uploader, YouTubeVisibility(client)),
            validator=YouTubeValidator(),
        )
