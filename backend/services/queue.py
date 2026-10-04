from asgiref.sync import sync_to_async

from . import tasks
from .core.ports import TaskQueue


class CeleryTaskQueue(TaskQueue):
    @sync_to_async
    def run_target(self, target_id: int) -> None:
        tasks.run_target.delay(target_id)

    @sync_to_async
    def confirm_now(self, target_id: int) -> None:
        tasks.confirm_target.delay(target_id)

    @sync_to_async
    def confirm_later(self, target_id: int, delay_seconds: int) -> None:
        tasks.confirm_target.apply_async((target_id,), countdown=delay_seconds)
