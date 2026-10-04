from abc import ABC, abstractmethod
from datetime import datetime

from ..publications.created_publication import CreatedPublication
from ..publications.new_publication import NewPublication


class PublicationRepository(ABC):
    @abstractmethod
    async def is_asset_ready(self, owner_id: int, asset_id: int) -> bool: ...

    @abstractmethod
    async def get_daily_publication_limit(self, owner_id: int) -> int: ...

    @abstractmethod
    async def create_publication_within_limit(
        self, publication: NewPublication, since: datetime, limit: int
    ) -> CreatedPublication | None: ...
