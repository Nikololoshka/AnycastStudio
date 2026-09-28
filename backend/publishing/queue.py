from platforms.core.ports import TaskQueue

from . import tasks


class CeleryTaskQueue(TaskQueue):
    def run_target(self, target_id: int) -> None:
        tasks.run_target.delay(target_id)

    def confirm_now(self, target_id: int) -> None:
        tasks.confirm_target.delay(target_id)

    def confirm_later(self, target_id: int, delay_seconds: int) -> None:
        tasks.confirm_target.apply_async((target_id,), countdown=delay_seconds)
