from contextlib import AbstractContextManager

from django.db import transaction

from platforms.core.ports import UnitOfWork


class DjangoUnitOfWork(UnitOfWork):
    def atomic(self) -> AbstractContextManager:
        return transaction.atomic()

    def on_commit(self, action) -> None:
        transaction.on_commit(action)
