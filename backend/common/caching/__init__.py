from django.core.cache import cache

from platforms2.core.ports import Cache


class DjangoCache(Cache):
    async def get(self, key: str):
        return await cache.aget(key)

    async def set(self, key: str, value, seconds: int) -> None:
        await cache.aset(key, value, seconds)
