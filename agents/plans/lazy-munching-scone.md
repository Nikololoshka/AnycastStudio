# План: `backend/platforms` — единое ядро бизнес-логики

## Context

Бизнес-логика публикации и авторизации разнесена по трём местам:

- `publishing/`: `pipeline.py` (claim, validate→upload→publish, confirm, `_error_of`),
  `schedule.py`, `services.py` (create с лимитом, dispatch, cancel/retry),
  `publishers/*` (модель → вызовы платформы; X ещё и пишет в БД), `tasks.py`
  (решает, когда ставить confirm);
- `social/`: `services.py` (save, refresh с lease, disconnect), `sessions.py`
  (OAuth state), `providers.py`, логика в `views/callback.py`, `views/creator_info.py`;
- `platforms/`: HTTP, OAuth-провайдеры, протоколы загрузки — в основном
  свободные функции, читают `django.conf.settings`, `django.urls.reverse`.

Цель: `platforms/` — единственное место бизнес-логики (публикация, авторизация
платформ, данные платформ для UI), в ООП/SOLID-стиле и без Django. Django-приложения
становятся тонкими: модели, HTTP, Celery, ORM-адаптеры. Это чистый рефакторинг:
HTTP API, строки `status`/`error.type`, имена Celery-задач и расписание beat
не меняются, фронтенд и `media/` не трогаем, новых зависимостей нет. Слабые
места из `docs/publishing-flow.md` §9 не чиним — готовим под них место.

---

## Принятые решения

**Слои**
- `platforms/core/` — утилиты, базовые интерфейсы **и сценарии** (`core/publishing`, `core/auth`).
- В `platforms` нет ни одного `import django`. Конфиг — `PlatformConfig`
  (`HttpConfig`, `UploadConfig`, `public_origin`, шаблон redirect
  `{origin}/api/social/{name}/callback`) + `OAuthCredentials` для каждой платформы.
- Порты (`core/ports/`, все ABC): `TargetRepository`, `PublicationRepository`,
  `AccountRepository`, `OAuthSessionRepository`, `TaskQueue`, `UnitOfWork`,
  `Clock`, `Cache`. Возвращают DTO из `core`, не модели.
- Один корень сборки `config/wiring.py::container()` — ленивый, кэш
  сбрасывается по сигналу `setting_changed` (тесты с `override_settings`
  продолжают работать).
- `core` знает только интерфейс `PlatformCatalog` (`get`, `all`); реализация —
  `platforms/registry.py::build_registry(config)`. Сценарии получают каталог
  через конструктор.

**Платформы**
- Одинаковая вложенная форма:
  ```text
  <platform>/
  ├─ client.py        <P>Client(PlatformClient)
  ├─ auth/            provider.py, responses.py
  ├─ upload/          session.py, state.py, uploader.py
  ├─ publish/         publisher.py (+ metadata/status по надобности)
  ├─ options/         options.py, validator.py, capabilities.py
  └─ platform.py      build_<p>(config, credentials) -> Platform
  ```
  TikTok дополнительно: `account/creator_info.py` (`CreatorInfoService`).
  Платформенные папки не импортируют друг друга.
- `Platform` — композиция (frozen): `name`, `label`, `capabilities`,
  `provider: OAuth2Provider`, `publisher: Publisher`, `validator: Validator`,
  `options: OptionsParser`. Части делят один `<P>Client`.
- `Validator.validate(draft: PublicationDraft)`; `PublicationDraft` = title,
  description, hashtags, `MediaInfo` (size, mime, duration), разобранные options.
  `PublishJob` = `draft` + target id, platform, account id, external id, путь
  файла, `uploaded_media_id`, `resume_state`, `publish_at`.
- Стадии `Publisher`: `validate`, `upload`, `publish`, `confirm(job) ->
  NotReady | Published | ReadyToCommit`, `commit(job)`,
  `resolve_uncertain(job) -> Published | None` (дефолт `None`).
  На `ReadyToCommit` pipeline пишет `commit_started` в `resume_state`, затем
  вызывает `commit`; если отметка уже стоит — pipeline поднимает `MaybePublished`;
  отметку снимает только при однозначном отказе (`not retryable`). X переходит
  на эту схему; Instagram — поведение как сейчас.

**Стиль**
- Поведение — методы объектов, которым оно принадлежит
  (`YouTubeOptions.description_with(hashtags)`, `Pkce(verifier).challenge()`,
  `ResumeState.chunk_plan(...)`). Публичных свободных функций на уровне модуля
  нет; приватные `_x` внутри модуля допустимы.
- Внутренние значения — `@dataclass(frozen=True)`; `ResumeState` продвигается
  через `replace()`. Pydantic — только на границе (ответы платформ, `settings`
  из клиента → options). DTO с токенами — `field(repr=False)`.
- Ошибки: `core/errors.py::PlatformError(failure_type: FailureType, message,
  details, retryable)` с `as_failure()`. Подклассы: `ProviderError`
  (`transient` → `retryable`), `NeedsFreshToken`, `UploadCancelled`,
  `MediaMissing`, `MaybePublished`. `FailureType(StrEnum)` — те же строки.
  Доменные исходы: `NotFound`, `Conflict(reason)`, `LimitReached(limit)`,
  `AccountNeedsReauth(platform)`.
- `common/responses/`: таблица «доменное исключение → `api_response`» и
  декоратор `@domain_errors` на views. `social_callback` ловит их локально
  (ему нужен redirect).
- Мультиарендность: view находит строку методом репозитория с фильтром по
  владельцу (`find_for_owner`), промах → `NotFound` (→ 404), в сценарий
  передаёт проверенный id.
- Время только через `Clock` (UTC `datetime`); `resume_state` хранит ISO-время
  от `Clock` вместо `time.time()`.
- `TokenService.run(account_id, action, on_rejected=None)` — один refresh,
  один повтор; заменяет три копии (upload в pipeline, `_ask_for_confirmation`,
  `creator_info._query`).
- Сценарии сами ставят следующий шаг через `TaskQueue`
  (`run_target`, `confirm_later(id, delay)`); Celery-задачи — однострочники.
- `TargetStatus`/`FailureType` — `StrEnum` в `core`; модели строят `TextChoices`
  из них, значения те же.

**Тесты**
- Интеграционные Django `TestCase` остаются для адаптеров (SQL claim, lease,
  due), сквозного пути и views.
- Unit-тесты сценариев — на фейках портов в `platforms/tests/fakes/`
  (реализации тех же ABC) с управляемым `Clock`.
- Точка мока сети: `platforms.core.http.transport.requests.request`.

---

## Целевая структура

```text
platforms/
├─ core/
│  ├─ errors.py       PlatformError, FailureType, доменные исключения
│  ├─ config.py       PlatformConfig, HttpConfig, UploadConfig, OAuthCredentials
│  ├─ http/           Transport, RetryPolicy, FailureClassifier, PlatformClient,
│  │                  PlatformModel, ResponseParser
│  ├─ upload/         UploadSession(ABC), UploadDriver, ResumableState, TokenRejectionGuard
│  ├─ capabilities/   Capabilities, Scheduling, Validator(ABC), ValidationResult
│  ├─ auth/           OAuth2Provider(ABC), Identity, TokenBundle, Pkce,
│  │                  TokenService, AccountService, ConnectFlow
│  ├─ publishing/     TargetStatus, PublicationDraft, MediaInfo, PublishJob,
│  │                  Publisher(ABC), NotReady/Published/ReadyToCommit,
│  │                  PublicationPipeline, ConfirmationPoller, DeferredDispatcher,
│  │                  PublicationService, FailureMapper, ProgressRecorder
│  ├─ ports/          репозитории, TaskQueue, UnitOfWork, Clock, Cache
│  └─ platform.py     Platform, PlatformCatalog(ABC)
├─ youtube/ tiktok/ instagram/ x/     форма выше
├─ registry.py        build_registry(config) -> PlatformCatalog
└─ tests/  core/  fakes/  youtube/  tiktok/  instagram/  x/

config/wiring.py       container(): config из settings, registry, адаптеры, сценарии
common/responses/      + domain_errors
publishing/            models, views, serializers, tasks, repositories.py, queue.py, admin
social/                models, views, tasks, repositories.py, admin
```

### Откуда что переезжает

| Сейчас | Куда |
| --- | --- |
| `platforms/http/*`, `<p>/api.py` | `core/http/*`, `<p>/client.py` |
| `platforms/upload/*` | `core/upload/*` |
| `platforms/oauth/*` | `core/auth/*` |
| `platforms/capabilities/*` | `core/capabilities/*` |
| `publishing/pipeline.py` | `core/publishing/` (`PublicationPipeline`, `ConfirmationPoller`, `FailureMapper`, `ProgressRecorder`) |
| `publishing/schedule.py` | `core/publishing/DeferredDispatcher` |
| `publishing/services.py` | `core/publishing/PublicationService` |
| `publishing/publishers/<p>.py` | `platforms/<p>/publish/publisher.py` |
| `publishing/publishers/__init__.py`, `social/providers.py` | `platforms/registry.py` |
| `social/services.py` | `core/auth/TokenService`, `AccountService` |
| `social/sessions.py`, логика `views/connect.py`, `views/callback.py` | `core/auth/ConnectFlow` |
| `social/views/creator_info.py` (запрос + кэш) | `platforms/tiktok/account/creator_info.py` |
| ORM-запросы всех перечисленных | `publishing/repositories.py`, `social/repositories.py` |

---

## Шаги

Каждый шаг: код → `manage.py test --settings=config.settings.test` зелёный →
`makemigrations --check --dry-run` без изменений → коммит. Перед кодом —
скилл `caveman` (CLAUDE.md). Шаги с OAuth одобрены заранее; поведение не меняется,
ассерты `social/tests` не правятся.

0. **Базовая линия.** Полный прогон тестов, записать число; `makemigrations --check`.

1. **Фундамент.** `core/errors.py` (иерархия, `FailureType`), `core/config.py`,
   `core/ports/clock.py`, `core/http/*` в классах (`Transport` — единственный
   `requests.request`). `<p>/api.py` → `<p>/client.py`. `config/wiring.py` с
   `container()` и сбросом по `setting_changed`. Обновить мок-пути в
   `platforms/tests/base.py` и тестах, патчащих `platforms.http.*`.

2. **`core/upload`, `core/capabilities`, базовый `core/auth` без Django.**
   `UploadDriver`, `TokenRejectionGuard`, `Pkce`; `OAuth2Provider` получает
   `OAuthCredentials` и redirect из конфига вместо `settings`/`reverse`.
   `social/providers.py` временно строит провайдеров из `container()`.

3. **Порты, DTO, стадийный `Publisher`.** `core/ports/*`, `PublicationDraft`,
   `MediaInfo`, `PublishJob`, `TargetStatus`, результаты стадий, `Platform`,
   `PlatformCatalog`. Адаптеры `publishing/repositories.py`
   (`job_of` строит DTO, путь через `media.storage.absolute`, `MediaMissing`),
   `UnitOfWork` на `django.db.transaction`. Фейки в `platforms/tests/fakes/`.
   Четыре publisher (пока в `publishing/publishers/`) переходят на `PublishJob`.

4. **Сценарии публикации.** `PublicationPipeline`, `ConfirmationPoller`,
   `DeferredDispatcher`, `FailureMapper`, `ProgressRecorder` в `core/publishing`;
   `TaskQueue` на Celery в `publishing/queue.py`; двухфазный `ReadyToCommit` в
   pipeline. `publishing/tasks.py` — однострочники через `container()`.
   Константы окна/порогов — атрибуты классов. `publishing/tests/*` переходят на
   `container()`; unit-тесты сценариев на фейках (`platforms/tests/core/`).

5. **`PublicationService` и тонкие views.** create (лимит внутри
   `UnitOfWork.atomic()`, dispatch через `on_commit` → `TaskQueue`), cancel,
   retry. Доменные исключения + `@domain_errors` в `common/responses/`;
   `find_for_owner` в репозиториях; `publishing/views/publications.py` =
   разобрать → найти своё → вызвать → сериализовать.

6. **YouTube — эталон.** Вложенная структура, `YouTubePublisher` из
   `publishing/publishers/youtube.py` + `publish.py`, `YouTubeOptions`,
   `YouTubeValidator`, `build_youtube`. `platforms/registry.py`;
   `container()` берёт YouTube из реестра. Контрактный тест дефолтов
   (`publishing/tests/test_platforms.py`) — на новый путь.

7. **TikTok** + `CreatorInfoService` (порт `Cache`, адаптер на `django.core.cache`),
   `social/views/creator_info.py` тонкий.

8. **Instagram** (поведение publish без изменений, `resolve_uncertain` не переопределяется).

9. **X** на `ReadyToCommit`/`commit`; удалить `publishing/publishers/`, `PUBLISHERS`,
   `schedule.py`, `pipeline.py`, `services.py`. Тесты `platforms/tests/test_<p>_*.py`
   разложены по `platforms/tests/<p>/`.

10. **Авторизация.** `TokenService` (`get_valid`, lease-refresh, `run`),
    `AccountService` (save, disconnect/revoke), `ConnectFlow` (start: state +
    PKCE; complete: claim state → проверка владельца сессии → exchange →
    identity → save) поверх `social/repositories.py`. Views `connect`,
    `callback`, `accounts`, `social/tasks.py` тонкие. Удалить
    `social/services.py`, `sessions.py`, `providers.py`.

11. **Архитектурный тест** `platforms/tests/core/test_architecture.py`: в
    `platforms` нет импортов `django`, `publishing`, `social`, `media`,
    `accounts`, `common`, `config`; платформы не импортируют друг друга;
    у каждой платформы есть `client.py`, `auth/`, `upload/`, `publish/`,
    `options/`, `platform.py`; в `core` нет импортов платформ.

12. **Документация.** `CLAUDE.md` (Architecture, форма пакета платформы, File
    Placement, Testing — точка мока и фейки), `docs/architecture.md`,
    `docs/platforms/adding-a-platform.md`, пути в `docs/publishing-flow.md`,
    `docs/adr/0002-platforms-core.md` (порты+адаптеры, `platforms` без Django,
    двухфазный commit).

---

## Риски

- **Мок-путь сети** меняется на шаге 1 — пропущенный патч = тест в сеть.
  `settings.test` без сети, такой тест упадёт, а не пройдёт молча.
- **SQL claim/lease/due** переносится в адаптеры дословно (условные UPDATE);
  покрыт `test_instagram.py` (claim), `test_refresh_lease.py`, `test_deferred.py`.
- **Ленивый контейнер**: забытый сброс кэша → тесты с `override_settings` видят
  старый конфиг. Отдельный тест: после `override_settings` `container()` отдаёт новый.
- **Время в `resume_state`** меняет формат (float → ISO) — адаптер/сценарий
  читает оба формата, чтобы уже висящие в БД таргеты не сломались.
- **Объём** ~12 коммитов; после любого шага код рабочий.

## Verification

- После каждого шага: `cd backend && .venv/Scripts/python manage.py test --settings=config.settings.test`
  (число тестов ≥ базовой линии) и `.venv/Scripts/python manage.py makemigrations --check --dry-run`.
- Шаг 11 — архитектурный тест зелёный.
- Финал вручную: Redis + uvicorn + worker + beat + `npm run dev`; подключить
  YouTube, загрузить короткое видео, опубликовать на все подключённые
  платформы, дождаться `completed`/`scheduled`; отмена во время заливки;
  retry упавшего таргета; TikTok creator info в composer; отключение аккаунта.
- `cd frontend && npm test` — контрактный тест дефолтов YouTube.
