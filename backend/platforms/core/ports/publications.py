from abc import ABC, abstractmethod
from datetime import datetime

from ..publishing.request import CreatedPublication, NewPublication


class PublicationRepository(ABC):
    @abstractmethod
    def asset_ready(self, owner_id: int, asset_id: int) -> bool: ...

    @abstractmethod
    def daily_limit(self, owner_id: int) -> int: ...

    @abstractmethod
    def created_since(self, owner_id: int, since: datetime) -> int: ...

    @abstractmethod
    def create(self, publication: NewPublication) -> CreatedPublication: ...
