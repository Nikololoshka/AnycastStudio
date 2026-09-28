from .writer import TargetWriter


class ProgressRecorder:
    def __init__(self, writer: TargetWriter, target_id: int):
        self._writer = writer
        self._target_id = target_id
        self._last_percent = 0

    def __call__(self, uploaded: int, total: int, state: dict) -> None:
        percent = 100 if total == 0 else int(uploaded * 100 / total)
        if percent == self._last_percent:
            return
        self._last_percent = percent
        self._writer.set(self._target_id, progress=percent, uploaded_bytes=uploaded, resume_state=state)
