import asyncio
from collections.abc import Awaitable, Callable
from contextlib import aclosing
from dataclasses import replace
from functools import partial

from platforms2.core import (
    AwaitingConfirmation,
    NotReady,
    PlatformError,
    PlatformFailure,
    Published,
    PublishInteractor,
    PublishJob,
    ReadyToCommit,
    Scheduled,
)

CONFIRM_DELAYS_SECONDS = (10, 30, 60, 120)
CONFIRM_POLLS = 20
COMMIT_STARTED = "commit_started"


# Тестовый эскиз: путь одной цели публикации одной функцией, чтобы видеть
# порядок вызовов PublishInteractor. В реальном коде шаги разнесены по задачам
# очереди (run_target, confirm_target), а `storage["target"]` — это PublicationTarget в БД.
async def publish_flow_sketch(
    publishing: PublishInteractor,
    job: PublishJob,
    storage: dict,
    valid_token: Callable[[], Awaitable[str]],
    refreshed_token: Callable[[], Awaitable[str]],
) -> None:
    target = storage["target"]

    # Каждый вызов платформы идёт с действующим токеном. TOKEN_REJECTED — один раз
    # refresh и повтор. Второй отказ уходит наверх; TokenService к этому моменту
    # уже перевёл аккаунт в needs_reauth, если refresh не прошёл.
    async def with_token[T](action: Callable[[str], Awaitable[T]]) -> T:
        try:
            return await action(await valid_token())
        except PlatformError as error:
            if error.failure is not PlatformFailure.TOKEN_REJECTED:
                raise
        return await action(await refreshed_token())

    # Загрузка живёт только внутри этого воркера: состояние сессии в БД не пишется,
    # продолжать после смерти воркера нечего. Генератор отдаёт UploadProgress
    # только для полосы прогресса. Отмена — выход из цикла: aclosing закрывает
    # генератор, а с ним файл и upload-сессию.
    async def upload(access_token: str) -> str | None:
        last_percent = -1
        async with aclosing(publishing.upload(job, access_token)) as progress_events:
            async for progress in progress_events:
                # SQLite: пишем только на целых процентах, и каждая запись —
                # короткая транзакция между кусками, не вокруг сетевого вызова.
                if progress.percent != last_percent:
                    last_percent = progress.percent
                    target.update(progress=progress.percent, uploaded_bytes=progress.uploaded_bytes)
                if progress.done:
                    return progress.media_id
                if target["cancel_requested"]:
                    return None
        raise PlatformError(PlatformFailure.UNEXPECTED, "The upload ended without a media id")

    # Commit — шаг, который нельзя выполнить дважды (X: создание поста).
    # Метка ставится ДО вызова: если задача подтверждения умрёт посреди commit,
    # следующая не создаст второй пост, а спросит resolve_uncertain.
    async def commit(confirmed: PublishJob) -> Published:
        before = dict(target["confirmation_state"])
        target["confirmation_state"] = {**before, COMMIT_STARTED: True}
        try:
            # HTTP-клиент не должен повторять этот запрос сам (attempts=1).
            return await with_token(partial(publishing.commit, confirmed))
        except PlatformError as error:
            if error.failure in (PlatformFailure.NETWORK, PlatformFailure.UNEXPECTED):
                # Ответа нет или он непонятен — пост мог появиться.
                raise PlatformError(
                    PlatformFailure.UNCONFIRMED,
                    "The post may have been created; check the platform before publishing again",
                    details=error.message,
                ) from None
            # Платформа явно отказала — повтор безопасен, метку снимаем.
            target["confirmation_state"] = before
            raise

    def finish(published: Published) -> None:
        target.update(status="completed", published_url=published.url)

    # ── 1. Задача run_target: забрать цель ───────────────────────────────
    # В БД это условный UPDATE queued → validating. Только из queued: если воркер
    # умер, acks_late доставит задачу снова, но rowcount будет 0 и она выйдет.
    # Цель, застрявшую в validating / uploading / publishing со старым
    # last_activity_at, периодическая задача переводит в failed
    # ("The worker stopped; publish again"). Брошенные цели заново не забираются.
    if target["status"] != "queued":
        return
    target["status"] = "validating"

    try:
        if target["cancel_requested"]:
            target["status"] = "cancelled"
            return
        if not job.media.path.exists():
            raise PlatformError(PlatformFailure.MEDIA_MISSING, "The uploaded video is no longer on the server")
        # Здесь PlatformValidator проверяет draft по правилам платформы → PlatformFailure.INVALID.

        # ── 2. Загрузка ──────────────────────────────────────────────────
        # Всегда с нуля: ручной retry после failed тоже начинает новую загрузку.
        target.update(status="uploading", total_bytes=job.media.size_bytes, progress=0, uploaded_bytes=0)
        # Повторы transient-отказов — забота interactor'а: YouTube повторяет кусок
        # внутри той же сессии (num_retries SDK), байты заново не уходят.
        media_id = await with_token(upload)
        if media_id is None:
            target["status"] = "cancelled"
            return
        # media_id нужен publish и задачам подтверждения; пишется один раз за попытку.
        target.update(media_id=media_id, progress=100, uploaded_bytes=job.media.size_bytes)
        job = replace(job, media_id=media_id)

        if target["cancel_requested"]:
            target["status"] = "cancelled"
            return

        # ── 3. Публикация ────────────────────────────────────────────────
        # YouTube: выставить видимость или publishAt → Published / Scheduled.
        # TikTok, Instagram, X: платформа ещё обрабатывает файл → AwaitingConfirmation.
        target["status"] = "publishing"
        match await with_token(partial(publishing.publish, job)):
            case Published() as published:
                finish(published)
                return
            case Scheduled(url=url):
                target.update(status="scheduled", published_url=url)
                return
            case AwaitingConfirmation(confirmation_state=state):
                target.update(status="processing", confirmation_state=dict(state))

        # ── 4. Подтверждение ─────────────────────────────────────────────
        # В реальности каждый опрос — отдельная задача confirm_target через
        # confirm_later(delay) со своим claim; здесь — цикл с asyncio.sleep.
        # confirmation_state — единственное, что переживает задачу: опросы
        # по природе растянуты на минуты.
        for poll in range(CONFIRM_POLLS):
            await asyncio.sleep(CONFIRM_DELAYS_SECONDS[min(poll, len(CONFIRM_DELAYS_SECONDS) - 1)])
            job = replace(job, confirmation_state=target["confirmation_state"])

            # Прошлый проход начал commit и не дождался ответа: не повторять,
            # а спросить платформу, появился ли пост.
            if COMMIT_STARTED in job.confirmation_state:
                resolved = await with_token(partial(publishing.resolve_uncertain, job))
                if resolved is None:
                    raise PlatformError(PlatformFailure.UNCONFIRMED, "Check the platform before publishing again")
                finish(resolved)
                return

            match await with_token(partial(publishing.confirm, job)):
                case NotReady():
                    continue
                case Published() as published:
                    finish(published)
                    return
                case ReadyToCommit():
                    finish(await commit(job))
                    return

        raise PlatformError(
            PlatformFailure.UNCONFIRMED, "The platform did not confirm the publish in time; check it there"
        )

    except PlatformError as error:
        # Повтора на уровне задачи нет. Ручной retry сбрасывает media_id и
        # confirmation_state и начинает публикацию с нуля.
        target.update(
            status="failed",
            error={"failure": error.failure.value, "message": error.message, "details": error.details},
        )
