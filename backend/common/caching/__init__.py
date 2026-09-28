from django.core.cache import cache

from platforms.core.ports import Cache


class DjangoCache(Cache):
    def get(self, key: str):
        return cache.get(key)

    def set(self, key: str, value, seconds: int) -> None:
        cache.set(key, value, seconds)
