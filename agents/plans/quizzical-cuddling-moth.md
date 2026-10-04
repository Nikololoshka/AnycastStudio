# Переход с `platforms/` на `platforms2/`

## Context

В `backend/platforms2/` готовы четыре платформы на новом API: async (aiohttp,
YouTube — google-api-python-client через `asyncio.to_thread`),
`AuthorizationInteractor` / `PublishInteractor`, `PlatformFailure`,
`PlatformCatalog` + `PlatformConfigs`. Но **ничто вне `platforms2` его не
импортирует**, а всё приложение (`config/wiring.py`, репозитории, views,
задачи, ~40 тестов) сидит на старом `platforms/core`: сценарии
(`TokenService`, `AccountService`, `ConnectFlow`, `PublicationService`,
`PublicationPipeline`, `ConfirmationPoller`, `CommitGuard`,
`DeferredDispatcher`, `TargetWriter`), порты и синхронный
`Platform(provider, publisher, validator)`.

Чего в `platforms2` пока нет: сценариев, портов, тестов, архитектурного
теста, TikTok creator info как публичного API, проверки «client_id не
настроен». Порядок вызовов сценариев уже описан в
`authorization_flow_sketch.py` и `publish_flow_sketch.py`.

Решения (подтверждены):
- сценарии и порты переезжают в `platforms2/core` (async), `platforms/`
  удаляется, `platforms2` → `platforms`;
- Celery-задача = `asyncio.run(...)` со своей `aiohttp.ClientSession` и
  каталогом на время вызова; views — `async def` (decorators из
  `common/core/decorators.py::precondition` уже строят async-обёртки, ASGI);
- resume загрузки убирается: загрузка всегда с нуля, `resume_state` удаляется,
  зависшие цели переводит в failed периодическая задача;
- словарь ошибок — `PlatformFailure`: `error.failure` вместо `error.type` в
  API, БД и фронте.

⚠ Затрагивает OAuth/токены (`social/`, `platforms*/…/auth/`) — по CLAUDE.md
каждый шаг этой зоны требует явного одобрения.

## Шаги (каждый — отдельный коммит, тесты зелёные)

### 1. Страховочная сеть для `platforms2`
- `platforms2/tests/` по форме `platforms/tests/`: `core/`, `fakes/`,
  `<platform>/`. Тесты на `IsolatedAsyncioTestCase` (стандартная библиотека).
- Мок сети без новой зависимости: фейковая `aiohttp.ClientSession`
  (`request()` как async context manager, очередь ответов) в
  `platforms2/tests/fakes/http.py`; YouTube — `googleapiclient.http.HttpMockSequence`
  через подмену `YouTubeApi.videos`.
- Портировать сценарии отказов из `platforms/tests/<platform>/test_{auth,upload,status}.py`:
  каждый способ отказа платформы → ожидаемый `PlatformFailure`.
- `test_architecture.py`: `platforms2` не импортирует Django и приложения.
- Дыры, найденные по ходу: пустой `client_id/secret` → `PlatformError(MISCONFIGURED, "<SETTING> is not configured")`
  (раньше `OAuth2Provider._configured`).

### 2. Порты и сценарии в `platforms2/core`
- `core/ports/`: перенести `platforms/core/ports/*` с async-методами
  (`AccountRepository`, `OAuthSessionRepository`, `PublicationRepository`,
  `TargetRepository`, `TaskQueue`, `UnitOfWork`, `Clock`, `Cache`,
  `AccessTokens`). Из `TargetRepository` убрать resume, добавить выборку
  зависших целей.
- `core/auth/`: `TokenService` (lease + refresh, разбор `PlatformFailure` как
  в шаге 4 эскиза; `MISCONFIGURED` аккаунт не трогает), `AccountService`
  (revoke через `revoke_auth_token(AuthToken)`), `ConnectFlow`
  (`create_auth_request` → сессия; callback: claim state + проверка владельца →
  `create_auth_token` → `fetch_auth_profile`).
- `core/publish/`: `PublicationService`, `PublicationPipeline` (`run_target` из
  эскиза: claim, validator `validate(draft, media)`, upload-генератор с записью
  на целых процентах, `publish` → `Published/Scheduled/AwaitingConfirmation`),
  `ConfirmationPoller` + `CommitGuard` (`commit_started`, `resolve_uncertain`,
  `UNCONFIRMED`), `DeferredDispatcher`, `TargetWriter`, `StaleTargetSweeper`.
- TikTok creator info: публичный `TikTokCreatorInfo` (или метод платформы) +
  сценарий с кэшем через порт `Cache` — вместо `platforms/tiktok/account/`.
- `AccountStatus`, `OAuthSessionStatus`, `TargetStatus`, записи
  (`AccountRecord`, `NewPublication`, `NotFound`, `Conflict`…) — в `platforms2/core`.
- Тесты сценариев на фейках портов (`platforms2/tests/fakes/`), портировать
  `platforms/tests/core/test_{auth_services,pipeline,publication_service}.py`.
- После портирования удалить оба `*_sketch.py`.

### 3. Адаптеры Django
- `social/repositories.py`, `publishing/repositories.py`,
  `publishing/queue.py`, `common/transactions`, `common/caching` реализуют
  новые порты: async ORM Django 5.2 (`aget`, `aupdate`, `acreate`), блоки
  `transaction.atomic` — через `sync_to_async`. Claim остаётся условным UPDATE.
  Транзакции не держатся через сетевой вызов (сценарии и так разделяют).
- Модели: импорт статусов из `platforms2`; миграции
  `publishing`: удалить `resume_state`; data-миграция `error.type` →
  `error.failure` (таблица соответствия старых типов: authentication →
  token_rejected, authorization → scope_missing, rate_limit → rate_limited,
  platform → refused, validation → invalid, file → file_rejected,
  unknown → unexpected).
- `common/responses/domain.py`: доменные ошибки из `platforms2`.
- `publishing/views/serializers.py`: `error.failure`.

### 4. Wiring, задачи, views
- `config/wiring.py`: `Container.platform_configs` собирает `PlatformConfigs`
  из settings (`CREDENTIAL_SETTINGS`, `redirect_uri = PUBLIC_REDIRECT_ORIGIN +
  /api/social/<p>/callback`, `PLATFORM_CHUNK_BYTES`, `HTTP_TIMEOUT`,
  `UPLOAD_RETRY_ATTEMPTS`); `async with container().services() as services` —
  открывает `ClientSession`, строит `PlatformCatalog` и сценарии, закрывает сессию.
- `publishing/tasks.py`, `social/tasks.py`, `media/tasks.py`:
  `asyncio.run(...)`; добавить задачу и beat-расписание для `StaleTargetSweeper`.
- Views с сетью (`social/views/{callback,accounts,creator_info}.py`,
  `publishing/views/publications.py`) → `async def`; `connect` и
  `platforms` (capabilities, `as_json` того же формата) можно оставить sync.
- Перенести тесты приложений (`social/tests`, `publishing/tests`) с мока
  `requests.request` на фейковую сессию из шага 1.

### 5. Фронтенд
- `frontend/src/domain`: тип `failure: PlatformFailure` вместо `type`;
  `features/publications/TargetRow.tsx:85` → `error.${target.error.failure}`.
- Ключи `error.*` в `src/locales/{en,ru}/publications.json` для всех значений
  `PlatformFailure` (en и ru синхронно).
- Убрать отображение resume/«продолжу загрузку», если есть.
- Контракт-тест YouTube defaults TS ↔ Python перенаправить на
  `platforms2/youtube`.

### 6. Удаление старого и переименование
- Удалить `backend/platforms/`, `git mv platforms2 platforms`, заменить
  импорты `platforms2.` → `platforms.`.
- `requirements.txt`: убрать `requests`, если остался только в тестах
  (`media/tests`, `*/tests/base.py`) — переписать их; pin логгера `urllib3`
  в settings заменить на `aiohttp.client` / `googleapiclient`.
- Документы: ADR `0003-async-platforms.md` (async, без resume, PlatformFailure),
  CLAUDE.md (Tech Stack: aiohttp вместо requests; правила про
  `PlatformClient.send`, форму папки платформы, `resume_state`, мок сети,
  `FailureType`), `docs/platforms/*.md`, `backend/docs/publishing-flow.md`.

## Verification
- После каждого шага: `.venv/Scripts/python manage.py test --settings=config.settings.test`,
  `manage.py check`, `manage.py makemigrations --check`.
- Шаг 5: `npx tsc --noEmit`, `npm run lint`, `npm test`.
- Финал вручную: Redis + uvicorn + worker + beat + `npm run dev`; подключить
  аккаунт каждой платформы, опубликовать видео (YouTube сразу и
  отложенно, TikTok/Instagram/X с подтверждением), отключить аккаунт;
  убить воркер посреди загрузки → цель уходит в failed через sweeper;
  в логах нет токенов и URL с `code`.
