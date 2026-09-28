from ..core.config import PlatformConfig
from ..core.platform import Platform, PlatformFactory
from ..core.ports import Clock
from .account import CreatorInfoApi
from .auth import TikTokProvider
from .client import LABEL, TikTokClient
from .options import CAPABILITIES, TikTokValidator
from .publish import PublishStatusApi, TikTokPublisher
from .upload import DirectPostProtocol, TikTokUploader


class TikTokFactory(PlatformFactory):
    def build(self, config: PlatformConfig, clock: Clock) -> Platform:
        client = TikTokClient(config.http)
        uploader = TikTokUploader(DirectPostProtocol(client), config.upload, clock)
        return Platform(
            name=TikTokProvider.name,
            label=LABEL,
            capabilities=CAPABILITIES,
            provider=TikTokProvider.create(config),
            publisher=TikTokPublisher(uploader, PublishStatusApi(client), CreatorInfoApi(client)),
            validator=TikTokValidator(),
        )
