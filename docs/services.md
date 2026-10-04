# Пакет `backend/services`: как устроен и зачем нужен

`services` — бизнес-логика AnycastStudio: как подключается аккаунт платформы,
как живёт и обновляется его токен, как публикация превращается в загрузки на
платформы, как подтверждается результат и что делать с зависшей работой.

Почему логика вынесена в отдельный пакет, записано в
[ADR 0004](adr/0004-services-package.md); асинхронная модель — в
[ADR 0003](adr/0003-async-platforms.md); подробный разбор публикации со
слабыми местами — в [publishing-flow.md](publishing-flow.md). Этот документ —
карта пакета: что где лежит, кто кого вызывает и почему так.

---

## 1. Место в системе

```
views (sync)  ─┐
               ├─► container().run(...) ─► usecases ─► platforms/<p> ─► API платформы
tasks (Celery) ┘                              │
                                              └─► core/ports ◄── адаптеры в Django-приложениях
```

- **`platforms/`** знает, *как говорить* с YouTube, TikTok, Instagram и X:
  OAuth, загрузка, публикация, классификация ответов. Ничего не знает про
  аккаунты, публикации и базу.
- **`services/`** знает, *что и когда* делать: кому принадлежит аккаунт,
  когда обновить токен, в каком статусе таргет, можно ли повторить шаг.
- **Django-приложения** (`social`, `publishing`, `common`, `media`) — адаптеры:
  модели, вьюхи и репозитории, реализующие порты `services`.

Зависимость идёт в одну сторону: `services → platforms`. `services/core` и
`services/usecases` не импортируют Django, Celery, `asgiref` и приложения —
это проверяет `services/tests/test_architecture.py`. Поэтому use case можно
целиком протестировать на in-memory фейках, без базы и сети.

---

## 2. Структура

```text
services/
├─ wiring.py        контейнер: собирает use cases из портов и адаптеров
├─ queue.py         CeleryTaskQueue — реализация порта TaskQueue
├─ tasks.py         все Celery-задачи
├─ core/            общие значения и контракты, без поведения
│  ├─ accounts/     AccountRecord, AccountTokens, AccountStatus, OAuthSession*, ConnectOutcome
│  ├─ publications/ NewPublication, NewTarget, CreatedPublication, CreatedTarget, TargetStatus
│  ├─ domain/       доменные ошибки: NotFound, Invalid, Conflict, LimitReached, …
│  └─ ports/        асинхронные интерфейсы к базе, очереди, кэшу и часам
├─ usecases/
│  ├─ accounts/     ConnectFlow, AccountService, TokenService
│  ├─ publications/ PublicationService, PublicationPipeline, ConfirmationPoller,
│  │                CommitGuard, DeferredDispatcher, StaleTargetSweeper,
│  │                TargetWriter, FailureReport
│  └─ tiktok/       CreatorInfoService
└─ tests/           сценарии use cases + fakes/ портов
```

Только три модуля верхнего уровня — `wiring.py`, `queue.py`, `tasks.py` —
имеют право касаться Django и Celery. Это точки входа.

---

## 3. Точки входа: `wiring.py`

### `Container`

Синглтон (`container()` под `functools.cache`). Лениво, через
`cached_property`, создаёт то, что живёт весь процесс:

| Свойство | Что это | Реализация |
| --- | --- | --- |
| `platform_configs` | конфиги четырёх платформ из `settings` | `PlatformConfigs` |
| `clock` | текущее время и `sleep` | `SystemClock` |
| `targets` | таргеты публикаций | `publishing.repositories.DjangoTargetRepository` |
| `publication_rows` | публикации и дневной лимит | `publishing.repositories.DjangoPublicationRepository` |
| `accounts` | аккаунты и токены | `social.repositories.DjangoAccountRepository` |
| `oauth_sessions` | OAuth-сессии подключения | `social.repositories.DjangoOAuthSessionRepository` |
| `queue` | постановка задач | `services.queue.CeleryTaskQueue` |
| `cache` | кэш | `common.caching.DjangoCache` |

Адаптеры импортируются внутри свойств — так `services` не тянет Django-модели
при импорте и не создаёт циклов.

Redirect URI каждой платформы строится из `PUBLIC_REDIRECT_ORIGIN` и
`/api/social/{platform}/callback`. Сегмент X ограничен 4 МБ — это лимит X.

При изменении настроек (`setting_changed`, в тестах — `override_settings`)
контейнер сбрасывается, чтобы конфиги пересобрались.

### `Services`

Набор use cases, собранный **на одну aiohttp-сессию**. Всё, что ходит в сеть,
получает эту сессию через `PlatformCatalog`. Сессия открывается и
закрывается вокруг одного вызова:

```python
def run(self, work):
    async def scoped():
        async with self.services() as services:   # открыть aiohttp-сессию
            return await work(services)            # выполнить use case
    return async_to_sync(scoped)()                 # из sync-мира
```

Вьюхи и задачи синхронные, use cases асинхронные; `run` — единственный мост.
Вьюха никогда не конструирует use case сама:

```python
publication_id = container().run(lambda services: services.publications.create(publication))
```

`Container.open_session` — точка, куда тесты подменяют `FakeSession`.

### `queue.py`

`CeleryTaskQueue` реализует порт `TaskQueue` тремя методами:
`run_target` → `publishing.run_target`, `confirm_now` / `confirm_later` →
`publishing.confirm_target` (сразу или с `countdown`). Use cases ставят задачи
только через порт и не знают о Celery.

### `tasks.py`

| Задача | Что делает | Кто запускает |
| --- | --- | --- |
| `publishing.run_target` | `PublicationPipeline.run` — загрузка и публикация одного таргета | `PublicationService`, `DeferredDispatcher` |
| `publishing.confirm_target` | `ConfirmationPoller.confirm` — один опрос платформы | pipeline, сам poller, dispatcher |
| `publishing.dispatch_due_targets` | `DeferredDispatcher.dispatch` | beat, раз в 60 с |
| `publishing.sweep_abandoned_targets` | `StaleTargetSweeper.sweep` | beat, раз в 5 мин |
| `social.refresh_expiring_tokens` | `TokenService.refresh_expiring` | beat, раз в 30 мин |
| `media.sweep_upload_sessions` | `media.services.sweep_upload_sessions` | beat, раз в 15 мин |
| `media.sweep_unused_assets` | `media.services.sweep_unused_assets` | beat, раз в час |

Имена задач (`<area>.<task>`) — часть контракта: на них ссылается
`CELERY_BEAT_SCHEDULE` и уже стоящие в Redis сообщения. Менять их нельзя.

Celery настроен на `acks_late` и `prefetch=1`, у задач нет собственных
ретраев (`max_retries=0`): сообщение может прийти повторно, поэтому каждая
задача сначала **захватывает** работу (см. §6), а решение «повторять или нет»
принимает pipeline, а не Celery.

---

## 4. `core/`: значения, ошибки, порты

### Значения

Замороженные dataclass'ы — то, чем use cases обмениваются с репозиториями
вместо Django-моделей:

- `AccountRecord` (id, платформа, статус) — для проверок владения;
- `AccountTokens` — то же плюс токены (`repr=False`, чтобы не утечь в лог),
  срок жизни, `lease_until` и scopes; умеет `expires_within(now, margin)` и
  `stored_token()` → `AuthToken` платформы;
- `OAuthSessionRecord` — сессия подключения с `code_verifier` (PKCE);
- `NewPublication` / `NewTarget` — что прислал композер;
  `CreatedPublication` / `CreatedTarget` — что создалось;
- перечисления `AccountStatus`, `OAuthSessionStatus`, `ConnectOutcome`,
  `TargetStatus`.

`TargetStatus` задаёт группы, на которые опираются запросы:

- `running()` — `validating`, `uploading`, `processing`, `publishing`;
- `worked_on()` — то, что делает воркер прямо сейчас (без `processing`,
  там ждём платформу);
- `active()` — `queued` + `running()`.

### Доменные ошибки

Отказ API — это исключение из `core/domain/`, которое декоратор
`common/responses::domain_errors` превращает в статус ответа:

| Ошибка | `status` | HTTP | Когда |
| --- | --- | --- | --- |
| `NotFound` | `not_found` | 404 | нет строки **или она чужая** |
| `Invalid` | `invalid` | 400 | неверное поле (`publishAt` в прошлом) |
| `Conflict` | `conflict` | 409 | действие недопустимо в текущем статусе |
| `AccountNeedsReauth` | `conflict` | 409 | аккаунт нужно переподключить |
| `LimitReached` | `quota_exceeded` | 409 | дневной лимит публикаций |
| `Unavailable` | `server_error` | 500 | платформа не настроена или не отвечает |

Ошибки платформы (`PlatformError` с `PlatformFailure`) приходят из
`platforms/` и в API не выходят напрямую: в фоне они записываются в таргет,
во вьюхах — переводятся в доменную ошибку.

### Порты

Абстрактные async-классы. Use case зависит только от них; реализации — в
приложениях, фейки — в `services/tests/fakes/`.

| Порт | Зачем |
| --- | --- |
| `AccountRepository` | аккаунты владельца, токены, upsert после OAuth, лиз на refresh, `needs_reauth` / `revoked` |
| `OAuthSessionRepository` | старт, захват по `state`, завершение и чистка OAuth-сессий |
| `PublicationRepository` | готов ли файл, дневной лимит, создание публикации в пределах лимита |
| `TargetRepository` | `PublishJob` по таргету, захваты, обновление полей, отмена, ретрай, проверка владения |
| `TaskQueue` | поставить `run_target` / `confirm_now` / `confirm_later` |
| `Cache` | `get` / `set` с TTL |
| `Clock` | `now()` и `sleep()` — время в тестах управляется |
| `AccessTokens` | «дай действующий токен» + `run(account_id, action)` |

`AccessTokens.run` — общий приём для любого вызова платформы с токеном:
выполнить действие с текущим токеном; если платформа ответила
`TOKEN_REJECTED`, принудительно обновить токен и повторить **один раз**.
Реализует порт `TokenService`.

Каждый метод Django-репозитория — синхронная функция под `sync_to_async`,
поэтому транзакция никогда не переживает сетевой вызов: прочитать → закрыть →
сходить в платформу → открыть → записать.

---

## 5. `usecases/`

### 5.1. Аккаунты

#### `ConnectFlow` — подключение аккаунта по OAuth

**`start(owner_id, platform)`** (вьюха `connect`):

1. Неизвестная платформа → `NotFound`; не заданы client id/secret →
   `Unavailable` и ошибка в лог.
2. Удаляет просроченные OAuth-сессии (TTL — `OAUTH_SESSION_TTL`, 10 мин).
3. Генерирует `state` (32 байта), просит у платформы URL авторизации
   (с PKCE, если платформа его использует) и сохраняет сессию
   `pending` с `state` и `code_verifier`.
4. Возвращает URL, на который SPA отправляет браузер.

**`complete(platform, state, code, refused, requester_id)`** (вьюха
`callback`) возвращает `ConnectOutcome`, а не бросает ошибки — callback
всегда редиректит обратно в SPA с результатом:

1. Захватывает сессию: `pending → processing` условным UPDATE, только если
   она не старше TTL. Повторный или поддельный callback получает `INVALID`.
2. **Вторая проверка `state`**: сессию открыл тот же пользователь, чья кука
   на запросе. Иначе — `INVALID` и предупреждение в лог.
3. Пользователь отказался или нет `code` → `CANCELLED`.
4. Обменивает `code` на токен, читает профиль. Ошибка платформы → `FAILED`.
5. Сохраняет аккаунт через `AccountService.save`, сессию — `done`.

#### `AccountService`

- `save` — upsert аккаунта (тот же аккаунт платформы у того же владельца
  обновляется, а не дублируется).
- `disconnect` — проверяет владение (`NotFound` для чужого), пытается
  отозвать токен у платформы (неудача только логируется), затирает токены
  и ставит `revoked`.

#### `TokenService` — жизнь токена

Реализует `AccessTokens`. Константы — главное, что нужно знать:

| | |
| --- | --- |
| `REFRESH_MARGIN` 5 мин | токен, истекающий раньше, обновляется перед использованием |
| `REFRESH_AHEAD` 1 ч | фоновый refresh берёт токены, истекающие в течение часа |
| `REFRESH_LEASE` 2 мин | сколько держится блокировка на refresh |

- `valid(id)` — вернуть токен; если истекает в пределах 5 минут — `refresh`.
- `refresh(id)`:
  1. Берёт **лиз**: `refresh_lease_until` ставится условным UPDATE, только
     если лиз свободен или истёк. Это нужно, потому что web и воркер могут
     одновременно увидеть протухший токен, а многие платформы делают
     refresh-токен одноразовым: второй refresh тем же токеном сломал бы
     аккаунт.
  2. Не взял лиз — ждёт чужой refresh, опрашивая базу каждые 0.5 с до
     конца лиза. Дождался нового `expires_at` — отдаёт новый токен; аккаунт
     стал неактивным — `GRANT_REVOKED`; лиз истёк без результата — `NETWORK`.
  3. Взял лиз — обновляет токен у платформы, сохраняет, снимает лиз
     (только свой — сравнение по `until`).
- Нет refresh-токена или платформа ответила `GRANT_REVOKED` /
  `SCOPE_MISSING` → аккаунт `needs_reauth`, ошибка «This account must be
  reconnected». `MISCONFIGURED` дополнительно пишется в лог как ошибка
  конфигурации.
- Новый токен сливается со старым (`merged_with`): если платформа не
  вернула новый refresh-токен или scopes, сохраняются прежние.
- `refresh_expiring()` — задача beat: проходит по активным аккаунтам,
  истекающим в течение часа, обновляет; ошибки по одному аккаунту не
  останавливают остальные. Возвращает число реально обновлённых.

### 5.2. Публикации

Публикация — это видео + текст + набор **таргетов**, по одному на аккаунт.
Вся фоновая работа идёт на уровне таргета; каждый таргет живёт независимо.

#### Машина состояний таргета

```
                ┌──────── cancel ────────┐
                ▼                        │
 queued ──► validating ──► uploading ──► publishing ──┬──► completed
   │  ▲                                               ├──► scheduled   (YouTube: отложенная публикация)
   │  │                                               └──► processing ─┬─► completed
   │  └──── retry (из failed / cancelled)                  ▲  │         └─► failed
   │                                                       └──┘ confirm_target
   └── cancel ──► cancelled          любой рабочий статус ── ошибка ──► failed
```

#### `PublicationService` — то, что вызывают вьюхи

Отвечает за миллисекунды, тяжёлую работу отдаёт в очередь.

**`create(NewPublication)`**:

1. Файл есть, принадлежит владельцу и загружен → иначе `NotFound("media_asset")`.
2. `publish_at` в будущем → иначе `Invalid`.
3. Каждый аккаунт таргета принадлежит владельцу и совпадает по платформе →
   иначе `NotFound("social_account")`; аккаунт активен → иначе
   `AccountNeedsReauth`.
4. Создаёт публикацию с таргетами **в одной транзакции вместе с проверкой
   лимита** за последние сутки (лимит — поле `max_publications_per_day`
   пользователя). Превышен → `LimitReached`.
5. Каждый таргет отдаёт воркеру (`run_target`), **кроме** таргетов платформ
   с `Scheduling.DEFERRED_UPLOAD` (TikTok, Instagram, X) при `publish_at` в
   будущем: у них нет нативного планирования, поэтому загрузка ждёт своего
   времени и её запустит `DeferredDispatcher`. YouTube планирует сам —
   загружается сразу и получает `scheduled`.

**`cancel(owner_id, target_id)`** — проверяет владение (404 для чужого).
Отменить можно только активный таргет и не в `processing` (платформа уже
приняла видео) → иначе `Conflict("not_running")`. Ставит
`cancel_requested`; таргет в `queued` сразу становится `cancelled`, а
работающий pipeline заметит флаг сам.

**`retry(owner_id, target_id)`** — только из `failed` / `cancelled`, иначе
`Conflict("not_retryable")`. Сбрасывает таргет в `queued` (ошибка, флаг
отмены, media id и состояние подтверждения обнуляются) и снова отдаёт
воркеру по тем же правилам, что `create`. Это **явное решение человека**:
автоматически упавший таргет не повторяется.

#### `PublicationPipeline` — задача `run_target`

Одна попытка опубликовать один таргет:

1. **Захват**: `queued → validating` условным UPDATE. Не получилось
   (дубль сообщения, отменён, уже идёт) — выход без действий.
   Увеличивает `attempt_count`, очищает прошлую ошибку.
2. Читает `PublishJob` — всё, что нужно платформе, без моделей.
3. Проверяет флаг отмены.
4. **Валидация** валидатором платформы (длины, формат, размер) и наличие
   файла на диске. Ошибка → `INVALID` / `MEDIA_MISSING`.
5. **Загрузка**: статус `uploading`, `publish.upload(job, token)` — async
   генератор `UploadProgress`. Прогресс пишется **только при смене целого
   процента** (SQLite делят web и воркер). После каждого события
   проверяется отмена. Последнее событие несёт `media_id`.
6. **Публикация**: снова проверка отмены, статус `publishing`,
   `publish.publish(job, token)` → `PublishOutcome`.
7. `TargetWriter.record` переводит результат в статус. Если это
   `processing` — ставит первый опрос подтверждения через 10 с.

Загрузка и публикация идут через `AccessTokens.run`: протухший токен
обновится и шаг повторится один раз. Любое исключение → `failed` с
`FailureReport`; отмена → `cancelled`. Других повторов pipeline не делает:
отказ платформы (файл не принят, квота кончилась) от повторения не
исправится, а каждая попытка тратит невосстановимую квоту YouTube.

Загрузка не возобновляется: если воркер умер посреди неё, таргет добьёт
`StaleTargetSweeper`, и человек опубликует заново.

#### `TargetWriter`

Единственное место, которое пишет статус таргета. Каждая запись обновляет
`last_activity_at` — по нему sweeper и dispatcher отличают живую работу от
брошенной. Методы: `set`, `fail`, `cancel`, `finish` и `record(outcome)`:

| `PublishOutcome` | Статус |
| --- | --- |
| `Published(url)` | `completed` |
| `Scheduled(url)` | `scheduled` |
| `AwaitingConfirmation(state)` | `processing`, `confirmation_state` = state платформы + `confirming_since` + `polls: 0` |

#### `ConfirmationPoller` — задача `confirm_target`

Многие платформы принимают видео асинхронно (TikTok, Instagram, X
обрабатывают его после загрузки). Poller опрашивает платформу, пока она не
скажет «готово».

1. **Захват** опроса: таргет в `processing`, и `last_activity_at` не
   изменился с момента чтения (оптимистичная блокировка). Два одновременных
   `confirm_target` не опросят платформу дважды.
2. Спрашивает платформу `publish.confirm(job)`:
   - `NotReady` — ещё обрабатывается;
   - `ReadyToCommit` — видео готово, нужен финальный **неидемпотентный**
     шаг (у X — создание поста) → `CommitGuard.commit`;
   - `Published` — готово → `completed`.
3. Не готово:
   - прошло больше 30 минут с `confirming_since` → `failed`
     (`UNCONFIRMED`: «проверьте на платформе»);
   - иначе `polls + 1` в `confirmation_state` и следующий опрос через
     10 → 30 → 60 → 120 → 120… секунд.

Всё состояние опроса лежит в `PublicationTarget.confirmation_state`, а не в
памяти задачи, поэтому подтверждение переживает рестарт воркера.

#### `CommitGuard` — защита от двойного поста

Неидемпотентный шаг нельзя повторить вслепую: если ответ потерялся, пост
мог создаться, и повтор даст дубль.

- `commit(job)`: **до** вызова платформы пишет в `confirmation_state` метку
  `commit_started`. Дальше:
  - успех → `Published`;
  - `NETWORK` / `UNEXPECTED` (ответа не получили) → метка остаётся, ошибка
    `UNCONFIRMED`: «пост мог быть создан, проверьте <платформу>»;
  - любой другой отказ (платформа точно ответила «нет») → метка снимается,
    исходная ошибка пробрасывается.
- `was_started(job)` — есть ли метка. Если poller видит её (например,
  воркер умер посреди commit), он **не повторяет** commit, а вызывает
  `resolve(job)` → `publish.resolve_uncertain`: платформа пытается найти
  уже созданный пост. Нашла — `completed`; нет — `UNCONFIRMED`.

#### `DeferredDispatcher` — задача beat раз в минуту

1. Находит таргеты `queued` платформ с отложенной загрузкой, у которых
   наступил `publish_at`, захватывает каждый (ставит `last_activity_at`) и
   отдаёт в `run_target`. Таргет, отправленный менее 15 минут назад, не
   переотправляется — защита от двойной постановки, если воркер занят.
2. Находит таргеты `processing`, у которых больше 5 минут не было
   активности (цепочка `confirm_later` потерялась, например, при рестарте
   Redis), и ставит им `confirm_now`.

#### `StaleTargetSweeper` — задача beat раз в 5 минут

Таргеты в `validating` / `uploading` / `publishing` без активности 15
минут — их бросил остановленный воркер. Переводит в `failed` с сообщением
«The worker stopped before the publish finished; publish again».
`processing` не трогает — там ждут платформу, им занимается poller.

#### `FailureReport`

Превращает исключение в JSON ошибки таргета: `PlatformError` — как есть;
`FileNotFoundError` — `MEDIA_MISSING`; всё прочее — `UNEXPECTED` с **именем
класса**, а не текстом (текст исключения `aiohttp` содержит URL и может
содержать секреты).

### 5.3. TikTok: `CreatorInfoService`

TikTok требует перед публикацией показать пользователю данные создателя
(ник, доступные уровни приватности, лимиты длительности). `info(owner_id,
account_id)`:

1. Аккаунт принадлежит владельцу и это TikTok → иначе `NotFound`.
2. Аккаунт `needs_reauth` → `AccountNeedsReauth`.
3. Ответ кэшируется на 5 минут по `tiktok-creator-info:<id>`.
4. Ошибка токена (`TOKEN_REJECTED` после повтора, `GRANT_REVOKED`,
   `SCOPE_MISSING`) → `AccountNeedsReauth`; прочие → `Unavailable`.

Это единственный use case, привязанный к одной платформе, поэтому он лежит
отдельно и получает `TikTokCreatorInfo` напрямую.

---

## 6. Сквозные приёмы

**Захват перед работой.** Celery с `acks_late` гарантирует «хотя бы
один раз»: сообщение может прийти дважды. Каждая задача начинает с условного
UPDATE, и только rowcount = 1 даёт право работать:

| Захват | Условие |
| --- | --- |
| `claim_queued_target` | `status = queued` → `validating` |
| `claim_confirmation_poll` | `status = processing` и `last_activity_at` не изменился |
| `claim_due_targets` | `queued`, срок наступил, не отправлялся 15 мин |
| `claim_stalled_confirmations` | `processing`, тишина 5 мин |
| `fail_abandoned_targets` | рабочий статус, тишина 15 мин |
| `claim_pending_session` | OAuth-сессия `pending` → `processing` |
| `try_lock_token_refresh` | лиз свободен или истёк |

В SQLite нет `SELECT … FOR UPDATE SKIP LOCKED`, поэтому везде условный
UPDATE.

**Короткие транзакции.** Ни одна транзакция не держится во время сетевого
вызова — иначе воркер заблокирует файл базы для web-процесса.

**Редкие записи.** Прогресс загрузки пишется на целых процентах, а не на
каждом чанке.

**Не повторять решение платформы.** Повторяется только отказ токена (один
раз, через `AccessTokens.run`) и транзиентные сбои внутри `PlatformHttp`
(через `RetryPolicy`, где повтор безопасен). Всё остальное — `failed`, и
решение о повторе за человеком.

**Чужое — это 404.** Владение проверяется в запросе
(`get_connected_account`, `ensure_target_owned`), а не после чтения.

**Секреты не уходят в логи.** Токены — `repr=False`, ошибки пишутся по
классу, `aiohttp` зажат до WARNING.

---

## 7. Тесты

- `test_account_scenarios.py`, `test_publication_scenarios.py`,
  `test_creator_info.py` — `IsolatedAsyncioTestCase` на фейках из
  `services/tests/fakes/` (`accounts.py`, `publishing.py`, `clock.py`) и
  фейковой платформе из `platforms/tests/fakes/`. Без базы и Django: здесь
  проверяются переходы статусов, окна времени, лизы и захваты.
- `test_wiring.py` — изменённая настройка доходит до конфига платформы,
  redirect идёт через `PUBLIC_REDIRECT_ORIGIN`, секрет не попадает в `repr`.
- `test_architecture.py` — границы импортов и «поведение в классах».
- Путь через настоящие репозитории и вьюхи тестируется Django `TestCase` в
  приложениях, с `FakeSession` вместо `Container.open_session`.

Запуск: `.venv/Scripts/python manage.py test --settings=config.settings.test`.

---

## 8. Как добавить новое

- **Новое правило про публикации или аккаунты** — метод или класс в
  `usecases/`; нужен новый доступ к базе — метод в порту `core/ports/`,
  реализация в репозитории приложения, фейк в `tests/fakes/`.
- **Новый вызов из вьюхи** — экземпляр в `Services.__init__`, вызов через
  `container().run(lambda services: …)`. Только если отвечает за
  миллисекунды; иначе — задача.
- **Новая фоновая задача** — функция в `tasks.py` с именем
  `<area>.<task>`, при необходимости строка в `CELERY_BEAT_SCHEDULE`.
  Начинать с захвата.
- **Новая платформа** — `platforms/<p>/`, каталог и конфиги, плюс её
  конфиг в `Container.platform_configs`. Use cases менять не нужно: они
  работают через `PlatformRegistry`. См.
  [adding-a-platform.md](platforms/adding-a-platform.md).
- **Новый исход API** — новая доменная ошибка и строка в
  `common/responses/`, а не новая форма тела ответа.
