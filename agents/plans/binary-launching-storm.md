# AnycastStudio: с Tauri-десктопа на web-приложение

## Context

В репозитории две несвязанные половины:

- `frontend/` — Tauri 2 десктоп (React 19 + RTK + HeroUI 3 + Tailwind 4, ~6.2k строк TS + ~2k строк Rust). Четыре платформы реализованы: OAuth через локальный loopback, токены в OS keyring, чанковые аплоады в Rust, планировщик в памяти.
- `backend/` — Django 5.1 «OAuth broker» (~1.2k строк) ровно для одного сценария: провести Facebook/Instagram OAuth за десктоп и отдать ему access token.

Цель — веб-приложение: браузер + бэкенд, который владеет токенами, файлами и публикацией. Загрузка должна продолжаться после закрытия вкладки.

### Решения (зафиксированы, не пересматриваются)

**Продукт и объём**

1. Мульти-юзерная архитектура, но **закрытый круг**: пара человек, аудиты платформ не нужны.
2. Аккаунты заводит админ через Django admin. **Регистрации нет, почты нет, сброса пароля нет.** Админка не публикуется — доступ через SSH-туннель.
3. **В объёме только YouTube.** Код X, Instagram и TikTok удаляется из рабочего дерева и достаётся из тега `v0-desktop`, когда дойдут руки.
4. Один аккаунт на платформу (ограничение в сервисе; схема поддерживает N).
5. **Расписание — только native YouTube** (`privacyStatus: private` + `status.publishAt`). Модели `ScheduledJob`, beat-тика расписания и порта `planSchedule.ts` в v1 нет.
6. Композер сохраняет вкладки «Общее | YouTube». Веб-навигация со страницами; мобильная вёрстка вне объёма.
7. Список публикаций (`/publications`) есть. Ленты событий (`PublicationEvent`) нет — её работу делают `status` + `error` на таргете и логи воркера.

**Техника**

8. Расширяем существующий Django. **DRF не вводим** — плоские view на существующем `guard()`/`api_response()` + pydantic для валидации тела.
9. **SQLite** (WAL, busy_timeout, захват задач условным UPDATE).
10. **Tauri удаляется полностью** в Фазе 0. Десктоп не нужен.
11. Сессионная cookie, не JWT.
12. **Celery + Redis**; Redis поднимается `docker run -p 6379:6379 redis:7-alpine`. **Ни Dockerfile, ни docker-compose.yml, ни nginx.conf в репозитории не остаётся.**
13. Прогресс — **поллинг** (`pollingInterval` в RTK Query). SSE не делаем.
14. Ключи платформ — в `backend/.env`. Пользовательских ключей (BYO credentials) нет.
15. Лимиты — именованные константы в настройках: файл ≤ 4 ГиБ, квота 10 ГиБ на пользователя, удаление медиа через 48 ч после завершения всех таргетов.
16. Внутренний ретрай загрузки переносим дословно; ретрай упавшего таргета — только вручную; отмена на лету есть.
17. Черновик композера — в `localStorage`. Незавершённая загрузка возобновляется после перезагрузки страницы с переподтверждением файла.
18. Vitest только на чистые функции. Django-тесты обязательны.
19. Переименование всего в AnycastStudio — разом, в Фазе 0.
20. `backend/.env` (всё секретное) + `frontend/.env.local` (только `VITE_API_URL`). Ни одного секрета в `VITE_*`.
21. Интерфейс на `en` и `ru`, оба файла синхронны.

**Эксплуатация**

22. **v1 работает только локально.** Деплой, TLS, nginx, бэкапы и ротация логов — вне объёма.
23. Redirect URI — `http://localhost:5173/api/social/youtube/callback` (Google разрешает `http://localhost` с любым портом для клиента типа **Web application**).

---

## Состояние на входе (проверено)

1. **`git log` пуст** — ни одного коммита, всё untracked. Корневого `.gitignore` нет, при этом на диске лежат `backend/.env` и `backend/db.sqlite3`.
2. **Фронтенд не собирается**: `frontend/src/services/logs` отсутствует, но импортируется из пяти файлов (`app/store/loggingMiddleware.ts`, `components/AppShell/AppTopBar.tsx`, `platforms/tiktok/tiktokUploadCommand.ts`, `services/scheduler/SchedulerService.ts`, `services/upload/UploadManager.ts`). `node_modules` не установлен. Чинить не будем — этот код удаляется.
3. **Секреты в бандле фронта**: `VITE_YOUTUBE_CLIENT_SECRET`, `VITE_X_CLIENT_SECRET`, `VITE_TIKTOK_CLIENT_SECRET`, `VITE_FACEBOOK_BROKER_TOKEN`. Считаем скомпрометированными, ротируем в Фазе 3.
4. Окружение: Windows 11, Docker Desktop 29.4.1, WSL2, Python 3.13.5. Redis нативно под Windows не существует — отсюда `docker run`.

Три латентных бага, которые не переносим как есть (актуальны, когда вернутся остальные платформы): `x_upload.rs` не опрашивает `STATUS` после `FINALIZE`; `instagram_upload.rs` не опрашивает `status_code` контейнера перед `media_publish`; `TikTokAdapter.publish()` безусловно возвращает `{success: true}`. Плюс в `oauth.rs` параметр `state` разбирается, но **никогда не сверяется** — на сервере это обязательная проверка.

---

## Целевая архитектура

```
Браузер
  │
  ▼
Vite dev server :5173 ──proxy /api──► uvicorn :8000 ──► SQLite (WAL)
  │  отдаёт SPA                          │          └─► Redis (broker)
  │  ← same-origin, cookie+CSRF          ▼
  │                              celery worker -B ──► ./media ──► YouTube Data API
  └── поллинг GET /api/publications/:id раз в 2 с
```

SPA и API — **один origin** через прокси Vite. Это делает cookie-сессию и CSRF тривиально правильными и убирает CORS полностью. Оно же определяет redirect URI: браузер после согласия Google возвращается на `http://localhost:5173/api/social/youtube/callback`, и прокси доносит запрос до Django.

Следствие, которое надо принять: **Vite dev server обязан быть запущен, чтобы работал OAuth.** Для локального v1 это нормально.

Процессы при разработке — четыре: `docker run redis`, `uvicorn`, `celery -A config worker -B`, `npm run dev`. Beat встраивается в воркер флагом `-B`, чтобы не плодить пятый процесс: расписания публикаций в v1 нет, beat нужен только для уборок и обновления токенов.

### Структура репозитория

```
/
├─ CLAUDE.md                  ← переезжает из .claude/ и переписывается
├─ README.md                  ← новый
├─ .gitignore                 ← корневой
├─ docs/
│   ├─ architecture.md · api.md · platforms/youtube.md
│   ├─ adr/0001-web-migration.md
│   └─ legacy/PRD-desktop.md  ← бывший agents/prd/PRD.md
├─ backend/
│   ├─ .env / .env.example
│   ├─ config/         settings/{base,dev,test}.py, urls, asgi, celery.py
│   ├─ common/         api_response, guard, validate(pydantic), EncryptedTextField, ratelimit
│   ├─ accounts/       User, Quota, auth-views
│   ├─ social/         SocialAccount, OAuthSession, реестр провайдеров, connect/callback
│   ├─ media/          MediaAsset, UploadSession, чанковые ручки, storage, уборка
│   ├─ publishing/     Publication, PublicationTarget, pipeline, tasks
│   ├─ platforms/      обычный python-пакет, НЕ Django-app:
│   │   ├─ base.py     PlatformProvider / PlatformPublisher, Capabilities
│   │   ├─ http.py     classify() + with_retry() + jitter  ← порт общего Rust-каркаса
│   │   └─ youtube/    oauth.py, upload.py, publish.py, capabilities.py, settings.py
│   └─ tests/
└─ frontend/
    ├─ .env.local              ← только VITE_API_URL
    └─ src/
        ├─ api/        baseApi, authApi, accountsApi, mediaApi, publicationsApi, platformsApi
        ├─ app/        store, router (react-router 7), providers, i18n
        ├─ domain/     чистые типы — DTO-зеркала бэкенда
        ├─ features/   auth, composer, publications, accounts, settings
        ├─ services/   chunkedUpload.ts  ← единственный выживший сервис
        ├─ components/
        └─ locales/{en,ru}/
```

`backend/platforms/` намеренно не Django-приложение: это прямой аналог `frontend/src/platforms/`, импортируемый из задач без зависимости от моделей. Правило «папка платформы самодостаточна, кросс-импортов нет» сохраняется.

---

## SQLite: правила игры

Писать в базу будут три процесса (web, worker, beat внутри воркера). Это работает при соблюдении ограничений, и они становятся архитектурными правилами:

1. **WAL и busy_timeout обязательны:**
   ```python
   DATABASES["default"]["OPTIONS"] = {
       "timeout": 30,
       "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=30000;",
       "transaction_mode": "IMMEDIATE",   # Django 5.1, убирает SQLITE_BUSY при read→write
   }
   ```
2. **Никогда не держать транзакцию открытой во время сетевого вызова.** Воркер: прочитал → закрыл транзакцию → сделал HTTP-запрос к YouTube (минуты) → открыл транзакцию → записал. Это главное правило порта `UploadManager`; на Postgres это гигиена, на SQLite — вопрос жизни.
3. **Прогресс пишется не чаще раза в секунду на таргет.** В Rust событие шлётся на каждый чанк; при 8 МиБ чанках и гигабитном канале это десятки записей в секунду.
4. **`SELECT ... FOR UPDATE SKIP LOCKED` в SQLite нет.** Захват задачи — условный UPDATE с проверкой rowcount, ровно как в `multiposter/sessions.py::claim()`:
   ```python
   claimed = PublicationTarget.objects.filter(pk=pk, status="queued").update(status="validating")
   if not claimed:
       return          # забрал кто-то другой
   ```
5. **Кеш — не в SQLite и не LocMem.** Redis уже есть ради Celery, `CACHES` указывает на него; это заодно чинит `ratelimit.py`, чьи счётчики сейчас живут в памяти процесса (о чём в файле есть комментарий).
6. **Портируемость.** Никаких SQLite-специфичных функций, уникальность — через `UniqueConstraint`. `settings.py` уже умеет `DATABASE_ENGINE=postgresql`; переезд = переменная окружения + `dumpdata/loaddata`. Порог переезда — устойчивые `database is locked` в логах воркера.

---

## Потоки

### (a) Вход

```
GET  /api/auth/csrf    → ставит csrftoken cookie
POST /api/auth/login   → Set-Cookie: sessionid (HttpOnly, SameSite=Lax)
GET  /api/auth/me      → 200 {user} | 401 {"status":"unauthorized"}
POST /api/auth/logout
```

Пользователей создаёт `manage.py createsuperuser` / Django admin через SSH-туннель к `127.0.0.1:8000`. `register`, `verify`, `password/reset` и модель `EmailToken` из объёма исключены.

### (b) Подключение YouTube

```
POST /api/social/youtube/connect                    (cookie + CSRF)
  → OAuthSession(user=request.user, platform="youtube",
                 state=token_urlsafe(32), pkce_verifier=<encrypted>, status=pending)
  ← {status:"ok", auth_url}

window.location = auth_url        (полный редирект, не popup)
  → Google → 302 http://localhost:5173/api/social/youtube/callback?code&state
       claim(state)                          условный UPDATE pending→processing
       session.user == request.user           ← новая обязательная проверка
       provider.exchange_code(code, verifier)
       provider.fetch_identity(...)           → channel id, title, avatar
       SocialAccount.objects.update_or_create(access_token=<Fernet>, refresh_token=<Fernet>, …)
  ← 302 /settings/accounts?connected=youtube
```

`poll_token`, `views/poll.py`, `CLIENT_TOKENS` и `require_client_token` удаляются: браузер присутствует при редиректе, опрашивать нечего.

### (c) Загрузка и публикация

```
POST  /api/media/uploads {filename,size,mime,sha256} → {upload_id, chunk_size:8MiB, offset:0}
loop: PATCH /api/media/uploads/<id>  Upload-Offset: N  body=raw bytes
        → 200 {offset:N+len} | 409 {status:"conflict", offset:<серверный>}
      GET /api/media/uploads/<id> → {offset}           (проба после обрыва)
POST  /api/media/uploads/<id>/complete → сверка size+sha256 → MediaAsset(ready)

POST  /api/publications {media_asset_id, title, description, hashtags,
                         publish_at?, target:{platform:"youtube", settings}}
  → Publication + PublicationTarget(status=queued) → publish_target.delay(id)
  ← 201 {publication}
        ══ вкладку можно закрыть ══

worker: validate → upload(on_progress) → publish
        publish_at задан → privacyStatus=private при загрузке
                           + videos.update со status.publishAt
        дальше публикует сам YouTube, серверу делать нечего

браузер: GET /api/publications/<id> раз в 2 с, пока таргет активен
```

---

## Что выживает, что переезжает, что умирает

### Выживает почти без правок

| Путь | Комментарий |
|---|---|
| `src/components/*` кроме оконных | `PlatformGlyph`, `SettingSwitch/Number/Select`, `TimePicker`, `UploadProgress` — чистый UI |
| `src/platforms/youtube/{settings.ts,YouTubeSettingsPanel.tsx}` | UI настроек и нормализаторы; на бэкенде зеркалятся валидаторы, контрактный тест сверяет дефолты |
| `src/locales/*`, `src/styles.css`, `ThemeSync`, `LanguageSync`, `MotionConfig`, `app/i18n` | без изменений; добавляются неймспейсы `auth`, `upload`, `publications` |
| `src/features/composer/*` | единственная по-настоящему клиентская фича; правка одна — `VideoFile` |
| `src/domain/publication/types.ts` | `PublicationStatus`, `ErrorType`, `PublicationError` становятся контрактом по проводу. **Строки этих юнионов не менять** — Rust-теги ошибок уже сериализуются ровно в них |
| `src/domain/platform/types.ts` | `Platform` остаётся юнионом из четырёх значений; `PlatformCapabilities`, `SchedulingMode`, `ConnectedAccount` — DTO-зеркала |
| `src/domain/normalizeHashtags.ts` | остаётся для UX; на сервере переписывается как авторитетная версия |

### Переезжает в Python

| Откуда | Куда | Как |
|---|---|---|
| `services/upload/UploadManager.ts` (214 строк) | `publishing/pipeline.py` | 1:1. `runPhase` → `_run_phase(target, fn)` с тем же try/except → `set_target_error(to_publication_error(...))`. `dispatch(setPlatformProgress)` → запись в строку таргета с throttle. Форма правильная, не перепроектировать. В v1 нужны только `run_publication_task` и `run_native_schedule`; `stage`/`publish_staged` вернутся вместе с Instagram |
| `platforms/youtube/YouTubeAdapter.ts` — `publish`/`schedule` | `platforms/youtube/publish.py` | `PUT videos?part=status` с `status.publishAt` — обычный HTTP-вызов |
| `platforms/youtube/YouTubeAdapter.ts` — `getCapabilities`/`validate` | `platforms/youtube/capabilities.py` | отдаётся SPA через `GET /api/platforms`; фронт держит только тип |
| `platforms/youtube/YouTubeAuth.ts` | `platforms/youtube/oauth.py` (наследник `PlatformProvider`) | `getValidAccessToken(accountId)` → `SocialAccount.get_valid_access_token()` под блокировкой строки, иначе два воркера сожгут токен |
| `src-tauri/src/commands/youtube_upload.rs` (420 строк) | `platforms/youtube/upload.py` | см. ниже |
| `services/persistence/{AccountsStore,PlatformSettingsStore}.ts` | таблицы | |

### Умирает

`frontend/src-tauri/` целиком; все `@tauri-apps/*` из `package.json` и скрипт `npm run tauri`; `services/auth/*`; `services/filesystem/`; `services/persistence/{AppStore,AppDataFolder}.ts`; `services/upload/`; `services/scheduler/`; `platforms/{x,instagram,tiktok}/` целиком; `platforms/youtube/youtubeUploadCommand.ts`; `components/AppShell/{WindowControls.tsx,useWindowMaximized.ts}` и `getVersion()`; `features/history`; `multiposter/views/poll.py`, `sessions.check()`, `poll_token_hash`, `require_client_token`, `CLIENT_TOKENS`, `POLL_TIMEOUT/INTERVAL`; `backend/{Dockerfile,docker-compose.yml,deploy/nginx.conf}`; `backend/docs/facebook-redirect-api.md`.

`agents/prd/PRD.md` переезжает в `docs/legacy/PRD-desktop.md` с шапкой «описывает снятый с разработки десктоп».

Всё удалённое остаётся в теге `v0-desktop` и достаётся по SHA — особенно три аплоадера и три `<P>Auth.ts`, которые понадобятся, когда вернутся остальные платформы.

### О переносе `youtube_upload.rs`

Переписываем на Python, **используя Rust как исполняемую спецификацию** — переносим поток управления, а не выводим заново.

Сначала выделяем общий каркас в `platforms/http.py` (в Rust он дублировался в четырёх файлах, ~120 строк каждый раз):

```python
class Retry(Exception): ...
def classify(response) -> Outcome     # 429/5xx → retry, 401/403 → authentication, иначе platform
def with_retry(send, *, attempts=5) -> Response
def jitter_ms(attempt) -> int         # экспонента 1 с → 30 с с джиттером
```

Теги `UploadError` ложатся прямо на `ErrorType`, поэтому контракт с фронтом не меняется.

Дальше сам цикл: создать session URI (`POST` с `X-Upload-Content-Type/-Length`, прочитать заголовок `Location`), затем `while offset < total`: `PUT` чанк с `Content-Range`, считать `308` успехом, брать подтверждённый офсет из заголовка `Range` ответа. Два отличия от десктопа:

- **`session_uri` + `offset` сохраняются в `PublicationTarget.resume_state`** после каждого успешного чанка. В десктопе это отдавалось наружу через `error.details`, чтобы TS-слой мог обновить токен и продолжить; на сервере это ещё и защита от падения воркера.
- **Чанк 8 МиБ вместо 1 МиБ.** Одна мегабайтная порция выбиралась ради отзывчивого прогресса в окне; на сервере это восьмикратные накладные расходы на запрос.

Отмена: `Arc<AtomicBool>` + `State<YouTubeUploadCancellations>` → проверка `PublicationTarget.cancel_requested` между чанками. Та же семантика, то же место в цикле.

Прогресс: `Channel<UploadProgressEvent>` → колбэк `on_progress(uploaded, total)`, который не чаще раза в секунду пишет `progress`/`uploaded_bytes` в строку таргета. Форма данных не меняется (`uploadedBytes`/`totalBytes`/`percent`).

### `PlatformAdapter` разделяется на два протокола

TS-интерфейс смешивал авторизацию, описание возможностей и ввод-вывод. Разводим:

```python
class PlatformProvider(Protocol):          # platforms/base.py — только OAuth
    name: str; scopes: tuple[str, ...]; uses_pkce: bool
    def authorize_url(self, state, challenge) -> str
    def exchange_code(self, code, verifier) -> TokenBundle
    def refresh(self, refresh_token) -> TokenBundle
    def fetch_identity(self, access_token) -> Identity
    def revoke(self, token) -> None

class PlatformPublisher(Protocol):         # только публикация
    def capabilities(self) -> Capabilities
    def scheduling_mode(self, settings) -> SchedulingMode
    def validate(self, ctx) -> ValidationResult
    def upload(self, ctx, on_progress) -> UploadResult
    def publish(self, ctx) -> PublishResult
    def schedule(self, ctx) -> ScheduleResult | None
```

`ctx` — frozen dataclass, зеркало `AdapterPublication` (путь к файлу, title, description, hashtags, settings, publish_at, uploaded_media_id, геттер токена).

Во фронте `PlatformAdapter` схлопывается до дескриптора:

```ts
export interface PlatformDescriptor {
  getCapabilities(): PlatformCapabilities;             // из GET /api/platforms
  validate(draft: PublicationDraft): ValidationResult; // только UX; авторитет — сервер
}
```

`VideoFile.path: string` заменяется на `file: File` (клиент) + `mediaAssetId: string` (сервер).

---

## Бэкенд

### Приложения

`common`, `accounts`, `social`, `media`, `publishing` + не-Django пакет `platforms`. `multiposter` переименовывается в `social` со свежей `0001_initial` — сохранять нечего, единственная таблица держит строки с TTL 600 секунд.

`INSTALLED_APPS` вырастает до `contenttypes`, `auth`, `sessions`, `staticfiles`, `admin` + пять приложений. Middleware получает `SessionMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`. Комментарий в settings *«Deliberately minimal: no admin, auth, sessions or static files»* — самая перевёрнутая строка в репозитории; убрать отдельным осознанным коммитом.

Админка не публикуется: в v1 всё и так на localhost, а при будущем деплое `location /admin/` не проксируется — доступ через SSH-туннель.

### Модели

```python
# accounts
User(AbstractBaseUser, PermissionsMixin)
    email unique USERNAME_FIELD, display_name, is_active, is_staff,
    date_joined, locale('en'|'ru'), timezone, theme
    # PASSWORD_HASHERS: Argon2 первым
Quota(user 1:1)  max_storage_bytes, max_media_asset_bytes,
                 max_concurrent_uploads, max_publications_per_day
                 # дефолты — из констант настроек, см. ниже

# social
SocialAccount(user FK, platform, external_id, display_name, avatar_url,
    access_token=Encrypted, refresh_token=Encrypted, key_version,
    token_expires_at, scopes[], extra JSON,        # yt_channel_id
    status{active,needs_reauth,revoked}, last_refresh_at, last_error, connected_at)
    UniqueConstraint(user, platform, external_id)
OAuthSession(user FK, platform, state unique, pkce_verifier=Encrypted,
    redirect_after, status{pending,processing,done,error}, result JSON, created_at)
    # claim() из sessions.py переносится дословно

# media
MediaAsset(user FK, filename, mime_type, size_bytes, sha256, storage_path,
    duration_s, width, height, thumbnail_path,
    status{uploading,ready,failed,deleted}, created_at, expires_at)
UploadSession(user FK, media_asset FK null, upload_id uuid,
    declared_size, declared_sha256, received_bytes, chunk_size,
    status{open,completed,aborted,expired}, created_at, last_activity_at, expires_at)

# publishing
Publication(user FK, media_asset FK, title, description, hashtags[],
    publish_at null, created_at, updated_at)
PublicationTarget(publication FK, platform, social_account FK, settings JSON,
    status -> PublicationStatus,          # словарь из domain/publication/types.ts, без изменений
    progress, uploaded_bytes, total_bytes,
    uploaded_media_id,                    # videoId
    resume_state JSON,                    # {session_uri, offset}
    published_url, error JSON{type,message,details},
    attempt_count, cancel_requested, started_at, finished_at)
    UniqueConstraint(publication, platform)
```

`PublicationTarget.settings` — непрозрачный JSON, валидируемый при записи через `platforms/youtube/settings.py`. Это зеркалит существующее `PlatformSettings = Record<string, unknown>` и оставляет добавление платформы в границах одной папки.

Ограничение «один аккаунт на платформу» — проверка в сервисе подключения, не в схеме.

### Константы лимитов

Одним блоком в `config/settings/base.py`, чтобы менять в одном месте:

```python
MAX_MEDIA_ASSET_BYTES   = 4 * 1024**3      # 4 ГиБ на файл
MAX_STORAGE_BYTES       = 10 * 1024**3     # 10 ГиБ на пользователя
MEDIA_RETENTION_HOURS   = 48               # после завершения всех таргетов
UPLOAD_CHUNK_BYTES      = 8 * 1024**2
UPLOAD_SESSION_TTL_H    = 6                # брошенная сессия
ORPHAN_ASSET_TTL_H      = 48               # ассет без публикации
PROGRESS_WRITE_INTERVAL = 1.0              # сек, throttle записи прогресса
UPLOAD_RETRY_ATTEMPTS   = 5
MAX_CONCURRENT_UPLOADS  = 2
```

### API-слой: без DRF

`multiposter/views/common.py` уже задаёт контракт: `api_response(status, **fields)` со строковым `status` как главным дискриминатором, таблицу `HTTP_STATUS` и `guard()` — фабрику декораторов, **которая уже умеет и sync, и async**. Клиент у API ровно один, browsable API не нужен, сериализаторы дублировали бы типы, которые всё равно зеркалятся в TypeScript.

Чего не хватает — валидации тела. Добавляем `pydantic>=2` и ~80 строк в `common/`:

```python
@require_post
@rate_limit("publications")
@require_auth
@validate(CreatePublicationSchema)
def create(request, data): ...
```

`HTTP_STATUS` дополняется `invalid:400`, `forbidden:403`, `conflict:409`, `payload_too_large:413`, `quota_exceeded:409`.

### Аутентификация

- `sessionid`: `HttpOnly`, `SameSite=Lax`, backend `cached_db` (Redis-кеш поверх SQLite). `Secure` включается вместе с HTTPS — в локальном v1 выключен.
- CSRF: `CsrfViewMiddleware`, `GET /api/auth/csrf` для посева cookie, `X-CSRFToken` из `prepareHeaders` RTK Query. Убрать все `@csrf_exempt`, кроме OAuth-callback (это GET со своей защитой через `state`).
- Срок сессии 14 дней со скользящим продлением; смена пароля сбрасывает остальные сессии.

### Реестр провайдеров

`FacebookProvider` уже нужной формы (`build_auth_url` / `exchange_code` / `redirect_uri` через `reverse()`). Три изменения:

1. **PKCE** — `authorize_url(state, challenge)` / `exchange_code(code, verifier)`, S256. Verifier лежит зашифрованным в `OAuthSession` (в десктопе жил в замыкании JS).
2. **Refresh** — `refresh(refresh_token) -> TokenBundle`. Google не возвращает `refresh_token` при обновлении: сохранить логику «нет нового — оставить старый» из `toStoredCredential` и записывать результат в той же транзакции, что и вызов.
3. **`redirect_uri` собирается из `PUBLIC_ORIGIN`**, а не из `https://{PUBLIC_HOST}` — схема теперь переменная (`http://localhost:5173` локально).

`ExchangeError` остаётся как есть, включая критичный `raise ExchangeError(f"... {type(exc).__name__}") from None`, который не даёт `client_secret` утечь через текст исключения `requests`.

```python
path("api/social/<slug:platform>/connect",  views.connect,  name="social-connect")
path("api/social/<slug:platform>/callback", views.callback, name="social-callback")
path("api/social/accounts",                 views.accounts)
path("api/social/accounts/<int:pk>",        views.account)     # DELETE
```

`PROVIDERS = {"youtube": YouTubeProvider()}` — остальные три добавляются по одной строке, когда вернутся.

### Шифрование токенов

`cryptography` → `MultiFernet`, ~40 строк `common/fields.py::EncryptedTextField`. `django-fernet-fields` не берём — не поддерживается.

- `TOKEN_ENCRYPTION_KEYS` — список `v<N>:<urlsafe-b64-32B>` через запятую, новый первым; ротация = цикл пересохранения. `SocialAccount.key_version` помнит, чем записана строка.
- Ключ **не** выводится из `DJANGO_SECRET_KEY`.
- `__str__`/`__repr__` модели не трогают поля токенов; в админке исключены. Правило «`urllib3` придушен до WARNING» сохраняется — оно существует ровно для того, чтобы `client_secret` не попал в лог.

### Очередь

Celery + Redis. Redis поднимается вручную:

```
docker run -d --name anycast-redis -p 6379:6379 redis:7-alpine
```

Compose-файла и Dockerfile в репозитории нет — команда живёт в `README.md`.

```python
# config/celery.py
app.conf.update(
    task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 3 * 3600},
    beat_schedule={
        "sweep-upload-sessions":   {"schedule": 900.0,  ...},
        "sweep-expired-media":     {"schedule": 3600.0, ...},
        "refresh-expiring-tokens": {"schedule": 1800.0, ...},
    },
)
```

Воркер запускается с `-B` (встроенный beat) — расписания публикаций в v1 нет, beat нужен только для уборок и обновления токенов, отдельный процесс ради этого не оправдан.

Идемпотентность: задача принимает id и начинается с захвата условным UPDATE. `acks_late` даёт at-least-once, захват превращает это в effectively-once. Параллелизм воркера — `-c 2`, он же `MAX_CONCURRENT_UPLOADS`.

Зависимости в `requirements.txt`: `celery[redis]`, `redis`, `pydantic`, `cryptography`, `argon2-cffi`, `pillow`. `psycopg` — нет.

---

## Возобновляемая загрузка браузер → backend

Свой чанковый протокол — зеркало того, что уже отлажено в `youtube_upload.rs`. tus не берём (Django-реализации заброшены, `tusd` тянет отдельный сервис и auth-hook); S3/MinIO не берём (контейнер + креденшалы, а воркер всё равно обязан читать файл целиком, чтобы кормить его чанковому API YouTube). Пишем через абстракцию `MediaStorage`, чтобы подмена была правкой одного файла.

```
POST   /api/media/uploads  {filename,size_bytes,mime_type,sha256}
         → 201 {upload_id, chunk_size, offset:0, expires_in}
         → 413 payload_too_large | 409 quota_exceeded
GET    /api/media/uploads/<id>                  → {offset, size_bytes} | 410 expired
PATCH  /api/media/uploads/<id>  Upload-Offset: N, body = raw bytes
         → 200 {offset:N+len} | 409 {status:"conflict", offset} | 410
POST   /api/media/uploads/<id>/complete         → {media_asset} | 422 checksum_mismatch
DELETE /api/media/uploads/<id>
```

Серверные правила:

- Запись только дописыванием (`open(path,"ab")`) под блокировкой строки `UploadSession`; клиент шлёт чанки строго по одному.
- **Тело стримится**: итерируем `request`, а не трогаем `request.body`; `DATA_UPLOAD_MAX_MEMORY_SIZE` маленький.
- `chunk_size` выбирает сервер — тюнится без релиза клиента.
- sha256 считается инкрементально и сверяется на `complete`.
- Открытых сессий на пользователя — не больше `max_concurrent_uploads`.

Хранение: `./media/<user_id>/<asset_id>/source.<ext>`. Уборка: сессии `open` старше 6 ч → `aborted` + unlink; ассеты, у которых все таргеты завершились более 48 ч назад → unlink; ассеты без публикации старше 48 ч → туда же.

Возобновление после перезагрузки страницы: `upload_id` кладётся в `localStorage`; при возврате SPA запрашивает `GET /api/media/uploads/<id>`, показывает «продолжить загрузку `video.mp4`» и просит выбрать тот же файл, сверяя размер и префикс sha256 перед тем, как досылать с офсета.

---

## Прогресс в браузер

Поллинг. `publicationsApi.getPublication` с `pollingInterval: 2000`, включаемым, пока хотя бы один таргет в активном статусе (`validating`, `uploading`, `publishing`). Это одна строка конфигурации RTK Query против async-view, Redis pub/sub, keepalive и отдельного блока прокси, которых требовал бы SSE.

Когда поллинг начнёт мешать — вводить SSE; при двух пользователях это, вероятно, никогда.

---

## Фронтенд

### Чем заменяется каждая возможность Tauri

| Было | Файлы | Стало |
|---|---|---|
| `plugin-dialog` `open()` | `VideoDropZone.tsx` | `<input type="file" accept="video/*">` |
| OS drag&drop (`api/webview`) | `VideoDropZone.tsx` | HTML5 `dragover`/`drop` + `DataTransfer.files` |
| `get_file_metadata`, `read_file_chunk` | `FileReader.ts`, `VideoDropZone.tsx` | `File.size`/`File.type`; чанки — `file.slice(off, off+n)` (`Blob`, который `fetch` стримит без загрузки в память). `readVideoDetails()` сохраняется почти целиком: `convertFileSrc(path)` → `URL.createObjectURL(file)` |
| `WindowControls`, `useWindowMaximized`, `data-tauri-drag-region` | AppShell | удаляются; `AppTopBar` становится веб-хедером с навигацией и меню пользователя |
| `getVersion()` | `AppTopBar.tsx` | `__APP_VERSION__` через Vite `define` |
| `plugin-store` | `AppStore.ts` | тема и язык — `localStorage`; настройки платформы — на сервере |
| keyring | `SecureStorage.ts` + `secure_storage.rs` | `EncryptedTextField`; **токен не попадает в браузер никогда** |
| loopback OAuth | `oauthLoopback.ts` + `oauth.rs` | редирект браузера на `/api/social/youtube/connect` |
| `plugin-opener` | `YouTubeAuth.ts` | `window.location.assign(authUrl)` |
| `plugin-http` (обход CORS) | 7 файлов | неактуально — браузер больше не зовёт API платформ |

Отказ от `plugin-http` и есть то, что вынуждает всю архитектуру: браузер **не может** обратиться к `googleapis.com` с токеном (CORS + утечка секрета). Эти файлы существовали только потому, что Tauri обходил CORS.

### Роутинг

`react-router` v7. `src/app/router/index.ts` сейчас буквально `export {}` — заготовка ровно под это.

```
/login                                          публичный
/                  → redirect /compose
/compose           ComposerScreen               защищённые
/publications      список
/publications/:id  деталь: прогресс, ошибка, «Повторить», «Отменить»
/settings/accounts подключение/отключение YouTube
/settings/general  тема, язык
```

`ProtectedRoute` смотрит на `useGetMeQuery()`; 401 из любого запроса диспатчит `loggedOut` и редиректит.

### Композер

Вкладки сохраняются: **«Общее» | «YouTube»**. Разделение общих полей и платформенных — суть продукта из PRD §8–§10, и при возврате Instagram новая вкладка добавляется без перекройки.

Блок публикации: «Опубликовать сейчас» / «Запланировать» с датой и временем. Для YouTube «запланировать» означает `privacyStatus: private` + `status.publishAt` — это надо явно подписать в UI, иначе поведение выглядит непредсказуемым.

### Redux: клиентское против серверного

RTK Query уже в дереве (входит в `@reduxjs/toolkit` 2.12) — новой зависимости нет, что соответствует правилу CLAUDE.md «не добавляй зависимость, если существующая решает задачу». Текущие тунки (`connectPlatform`, `restoreAccounts`, `startPublication`) — рукописные loading/error/caching, которые RTKQ удаляет.

**Серверное состояние → RTK Query** (`src/api/`): `authApi`, `accountsApi`, `mediaApi`, `publicationsApi`, `platformsApi`.
Цикл PATCH-чанков — **не** эндпоинт RTKQ, а сервис `src/services/upload/chunkedUpload.ts` с `onProgress`/`signal`/resume. Единственный выживший файл в `services/`, написанный заново.

**Клиентское состояние → слайсы**: `composerSlice` (черновик + автосохранение в `localStorage`), новый `uploadSlice` (прогресс браузер→сервер, сервер его не видит до `complete`), `settingsSlice` (тема, язык).

**Удаляются**: `publicationsSlice`, `accountsSlice`, `features/history`.

Логика редьюсеров `setPlatformStatus`/`setPlatformProgress`/`setPlatformError` не пропадает — она становится тем, что возвращает сервер в `GET /api/publications/:id`.

### Тесты

Vitest + чистые функции: `normalizeHashtags`, валидация композера, арифметика офсетов в `chunkedUpload`. Компонентных тестов нет. Арифметика чанков — единственное место, где ошибка тихая и дорогая: битый файл обнаружится только по sha256 в конце четырёхгигабайтной загрузки.

---

## Фазы

Каждая фаза заканчивается зелёными `npx tsc --noEmit`, `npm run lint`, `python manage.py test` и ручным сценарием.

### Фаза 0 — зафиксировать прошлое, расчистить дерево

- `git add -A && git commit` всего текущего состояния, тег **`v0-desktop`**. Это архивный снимок, а не рабочая сборка: фронт не компилируется, и чинить его не нужно. Здесь навсегда остаются четыре Rust-аплоадера, три `<P>Auth.ts` и три адаптера — спецификация для будущего порта.
- Корневой `.gitignore`. **Перед коммитом убедиться, что `backend/.env` и `backend/db.sqlite3` не попали в индекс.**
- Удалить: `frontend/src-tauri/`, `frontend/src/platforms/{x,instagram,tiktok}/`, `backend/{Dockerfile,docker-compose.yml,deploy/}`, `backend/docs/facebook-redirect-api.md`.
- Переименовать всё в AnycastStudio: npm-пакет `scaffold`, Django-приложение `multiposter` → `social`, URL-префикс, `SERVICE_NAME`, имена логов.
- Разбить `config/settings.py` на `base/dev/test`; включить WAL, `busy_timeout`, `transaction_mode`; завести блок констант лимитов; `backend/.env.example` и `frontend/.env.local`.
- `docs/adr/0001-web-migration.md` с решениями из шапки этого плана; перенести PRD в `docs/legacy/`.
- **Готово когда:** `git log` показывает один коммит с тегом `v0-desktop` и один коммит расчистки; `python manage.py test --settings=config.settings.test` зелёный (487 строк существующих тестов должны пережить переименование).

### Фаза 1 — идентичность на бэкенде

- `common`: вынести `api_response`/`guard`/`ratelimit` из `social`, добавить `require_auth`, `validate(pydantic)`, новые коды в `HTTP_STATUS`, `EncryptedTextField`.
- `accounts`: `User` (email + Argon2), `Quota` с дефолтами из констант. Включить auth/sessions/CSRF/admin. **`AUTH_USER_MODEL` выставить до первой `migrate` для `django.contrib.auth`.**
- `/api/auth/{csrf,login,logout,me}`. Redis в `CACHES`.
- **Готово когда:** curl логинится, получает `/api/auth/me` по cookie и 401 без неё; rate-limit логина работает; `manage.py createsuperuser` + админка через туннель заводят пользователя; тесты `claim()` живы под новым label.

### Фаза 2 — фронтенд становится вебом

- Вырезать весь Tauri-зависимый код и остатки трёх платформ: `services/{auth,filesystem,persistence,upload,scheduler}`, `features/history`, `publicationsSlice`, `accountsSlice`, `capabilities.ts`, `auth.ts`, `SchedulerRunner` в `AppProviders`. Удалить `@tauri-apps/*` из `package.json`.
- `react-router`, `src/api/baseApi.ts` (CSRF-заголовок, обработка 401), `authApi`, экран входа, `ProtectedRoute`, веб-хедер, прокси `/api` в `vite.config.ts`.
- `VideoDropZone` на `File`; `VideoFile` получает `file: File` и `mediaAssetId`. Композер с вкладками «Общее | YouTube». Публикация заглушена явным disabled-состоянием.
- Vitest, первые тесты на `normalizeHashtags`.
- **Готово когда:** `grep -r @tauri-apps frontend/src` пуст; `npx tsc --noEmit` и `npm run lint` зелёные; пользователь логинится, видит композер, выбирает видео, видит превью и метаданные, и получает «публикация временно недоступна».

### Фаза 3 — подключение YouTube

- `social`: `SocialAccount`, `OAuthSession`, `PlatformProvider` + `YouTubeProvider` (PKCE S256, `access_type=offline&prompt=consent`, refresh с сохранением старого токена, `fetch_identity` по `channels?mine=true`, revoke при отключении), `connect`/`callback`/`accounts`, шифрование, проверка привязки `state` к пользователю, beat-задача `refresh_expiring`.
- В Google Cloud: сменить тип клиента с «Desktop app» на «Web application», добавить redirect URI `http://localhost:5173/api/social/youtube/callback`, **ротировать скомпрометированный `client_secret`**.
- Фронт: `accountsApi`, `PlatformAccountConnector`, `/settings/accounts`.
- **Готово когда:** пользователь подключает канал и видит его имя и аватар; в `db.sqlite3` поля токенов — шифротекст; отключение отзывает токен в Google; истёкший access token обновляется без участия пользователя; `state` одного пользователя не погашается в сессии другого.

### Фаза 4 — загрузка медиа

- `media`: модели, четыре ручки, `MediaStorage`, квоты, уборки, метаданные (`ffprobe` при наличии, иначе размеры с клиента), превью.
- `chunkedUpload.ts` с прогрессом, отменой, повтором чанка и возобновлением; `uploadSlice`; экран «продолжить загрузку» после перезагрузки страницы.
- **Готово когда:** файл 3 ГБ заливается; закрытие вкладки посреди загрузки и возврат предлагают продолжить с серверного офсета; подменённый файл отклоняется по sha256; превышение квоты даёт `quota_exceeded`; брошенная сессия исчезает после уборки.

### Фаза 5 — публикация на YouTube

- `publishing`: `Publication`, `PublicationTarget`, `pipeline.py` (порт `UploadManager` — `run_publication_task` и `run_native_schedule`), Celery + Redis, `platforms/http.py`, `platforms/youtube/{upload,publish,capabilities,settings}.py` с сохранением `resume_state`.
- `POST/GET /api/publications`, отмена, ручной «Повторить», `GET /api/platforms`.
- Фронт: `publicationsApi` с `pollingInterval`, `/publications`, `/publications/:id`, отправка публикации из композера.
- **Готово когда:** пользователь грузит видео, жмёт «Опубликовать», **закрывает вкладку** — ролик появляется на канале; открытая заново вкладка показывает корректный прогресс; перезапуск воркера посреди загрузки возобновляет её из `resume_state`; 401 от Google приводит к refresh и продолжению; «Запланировать» на +1 час создаёт приватное видео с `publishAt`, и YouTube публикует его сам; отмена прерывает загрузку между чанками; упавший таргет повторяется кнопкой и продолжает с офсета.

### Фаза 6 — сведение концов

- Перевод новых экранов на `en` и `ru`, синхронность ключей.
- Тесты: контрактный тест на совпадение дефолтов настроек YouTube в TS и Python; тесты pipeline; тесты чанкового протокола (включая 409 и обрыв).
- **Переписать `CLAUDE.md`** (см. ниже), написать корневой `README.md`, `docs/architecture.md`, `docs/platforms/youtube.md`.
- **Готово когда:** в `CLAUDE.md` нет упоминаний Tauri, Rust и десктопа; по `README.md` проект поднимается с нуля четырьмя командами.

**Не в объёме v1, возвращается из `v0-desktop` позже:** X, Instagram, TikTok; `ScheduledJob` и механика `stage`/`publishStaged`; SSE; `PublicationEvent`; регистрация и почта; пользовательские ключи платформ; деплой, TLS, nginx, бэкапы.

---

## Документация

### `CLAUDE.md` — что стало неверным

Файл переезжает из `.claude/` в корень. Конкретные места, ставшие ложными:

| Раздел | Сейчас | Станет |
|---|---|---|
| Заголовок / Project Snapshot | «Windows desktop client (Tauri…)», «Project type: Windows desktop app» | «Веб-приложение (Django + Celery, React SPA), запускается локально» |
| Never Do By Default | «Put business logic in Rust — it belongs in TypeScript» | «Бизнес-логика — в Django. SPA рисует и собирает ввод; публикация и токены принадлежат серверу» |
| Tech Stack → Core | «Database(s): none — no backend, no persistent DB», «Messaging/queueing: none», «Cache/storage: Tauri Store + OS keyring», «Hosting: none — local desktop app» | SQLite (WAL); Celery + Redis; Redis-кеш + каталог `media`; локальный запуск. **Все четыре строки сейчас прямо противоположны правде** |
| Key Libraries | строки Desktop shell / Auth (keyring, PKCE в TS) / Dialogs / Networking (reqwest) | удалить; добавить Django, Celery, Redis, pydantic, cryptography, RTK Query, react-router, Vitest |
| Version Policy | «`src-tauri/Cargo.toml` (Rust)» | `backend/requirements.txt` |
| Architecture | «thin native shell», «all business logic lives in TypeScript», «React UI → Redux → Application Services → Platform Adapters → Platform APIs» | «React SPA → REST → Django → Celery → Platform APIs»; перечисленные там `services/*` больше не существуют |
| Architectural Rules | «business logic must not live in `src-tauri/`» **и весь абзац-исключение** про «upload loop may live in a Rust command» | удалить. Новое правило: цикл загрузки живёт в `backend/platforms/<p>/upload.py`, вызывается только из Celery-задачи и никогда из обработчика запроса |
| Architectural Rules | «Every platform adapter implements `PlatformAdapter`» | «Каждая платформа реализует `PlatformProvider` и `PlatformPublisher` в `backend/platforms/base.py`; фронт держит только UI настроек» |
| Architectural Rules | «New Redux state goes in a feature slice» | дополнить: «Серверное состояние — эндпоинт RTK Query в `src/api/`; в слайс попадает только клиентское: черновик композера, прогресс браузерной загрузки, тема и язык» |
| Architectural Rules | «UI components call services, never platform adapters or Tauri commands, directly» | «UI-компоненты зовут хуки RTK Query, а не `fetch` напрямую» |
| Repository Structure / File Placement | весь блок `src/` и строка `src-tauri/src/commands/`; правило «anything needing OS access → Rust command» | новое двухкорневое дерево; «всё, что касается API платформы, токена или файла — это код бэкенда» |
| Environment Setup | «Rust toolchain», «`npm run tauri dev`», «No local services (DB, Docker, queue) are required», «Set `VITE_YOUTUBE_CLIENT_ID` in `.env.local`» (**клиентский секрет в Vite-переменной — теперь жёсткое нарушение**) | Node 24 + Python 3.13 + Docker (только ради Redis); четыре процесса; client id **и** secret живут в `backend/.env` и никогда в `VITE_*` |
| Development Commands | строка `npm run tauri dev` | `docker run redis`, `manage.py migrate/test`, `uvicorn`, `celery -A config worker -B`, `npm run dev`, `npm run test` |
| Security → Hard Rules | «OAuth tokens … через OS keyring (`secure_storage.rs`, keyring crate)» | «Токены живут только в `SocialAccount`, зашифрованные `EncryptedTextField`. Токен платформы не должен попасть ни в ответ API, ни в строку лога, ни в SPA». Пункт «никогда в Redux, никогда в localStorage» сохраняется и усиливается |
| Security → Sensitive Areas | пути `src/services/auth/*`, `oauth.rs`, `secure_storage.rs`, `.env.local` | `backend/social/`, `backend/platforms/*/oauth.py`, `backend/common/fields.py`, `backend/accounts/`, `backend/.env` |
| Tools | «@.cluade/RTK.md» | опечатка — исправить на `.claude` |

Новые разделы: **Мульти-тенантность** (каждый queryset фильтруется по `request.user`; `user_id` от клиента не принимается; до `PublicationTarget` можно дойти только через владельца), **Фоновая работа** (идемпотентность, захват до работы, ретраи, `acks_late`), **SQLite** (правила из раздела выше, особенно «не держать транзакцию во время сетевого вызова»), **Конвенции API** (контракт `{"status": …}`), **Тестирование**.

Правила, которые остаются: принципы агента, «no what-comments», HeroUI-first, токены темы вместо хардкода, i18n через `useTranslation` с синхронными `en`/`ru`, запрет коммитить секреты.

### Новый корневой `README.md`

```
# AnycastStudio
Одно видео → YouTube (дальше — X, Instagram, TikTok) из одной вкладки.
Загрузка продолжается после того, как вы её закрыли.

## Статус                   v1: только YouTube, локальный запуск
## Как это устроено         схема + 6 строк
## Требования               Node 24, Python 3.13, Docker (только ради Redis)
## Запуск                   docker run -d -p 6379:6379 redis:7-alpine
                            python manage.py migrate && python manage.py createsuperuser
                            uvicorn config.asgi:application --port 8000
                            celery -A config worker -B -c 2
                            cd frontend && npm i && npm run dev   → http://localhost:5173
## Конфигурация             таблица переменных backend/.env и frontend/.env.local
## Подключение YouTube      тип клиента Web application, scope, точный redirect URI,
                            ограничение квоты 10 000 юнитов/сутки
## Разработка               структура, команды, тесты, миграции
## Архитектура              ссылки на docs/
## Безопасность             что храним, как шифруем, политика удаления медиа
```

`backend/README.md` переписывается: он называет себя «OAuth broker for the desktop app» и ссылается на несуществующий `docs/API.md`.

---

## Верификация

Сквозной ручной сценарий после Фазы 5:

1. `docker run redis`, `uvicorn`, `celery -A config worker -B`, `npm run dev`.
2. Вход существующим пользователем; cookie HttpOnly в DevTools; без cookie `/api/auth/me` отдаёт 401.
3. Подключить YouTube; в `db.sqlite3` поля токенов нечитаемы; имя и аватар канала на месте.
4. Залить файл ~3 ГБ; посреди загрузки перезагрузить вкладку → предложено переподтвердить файл и продолжить с серверного офсета.
5. Опубликовать; **закрыть вкладку**; через минуту открыть `/publications/:id` — прогресс идёт, ролик доходит до канала.
6. Повторить загрузку и `taskkill` воркера посреди неё → после перезапуска загрузка продолжается из `resume_state`, а не начинается заново.
7. Запланировать на +1 час → видео на канале приватное, с `publishAt`; через час публикуется само.
8. Отменить идущую загрузку → останавливается между чанками, статус `cancelled`.
9. Отозвать доступ приложения в настройках Google-аккаунта и опубликовать снова → таргет падает с `type: "authentication"` и внятным текстом, кнопка «Повторить» доступна.
10. Завести второго пользователя через админку: чужие публикации, аккаунты и медиа недоступны (404, не 403).
11. В логах воркера нет `database is locked`.

Автоматически: `python manage.py test`, `npx tsc --noEmit`, `npm run lint`, `npx vitest run`.

---

## Риски и то, о чём надо помнить

1. **Квота YouTube — 10 000 юнитов в сутки на проект, `videos.insert` стоит ~1600.** Это около шести загрузок в сутки на всё приложение, независимо от числа пользователей. Для закрытого круга приемлемо, но: автоматический повтор упавшей публикации запрещён именно поэтому (повтор сжигает ещё 1600), а `Quota.max_publications_per_day` должен существовать с первого дня, чтобы приложение упиралось в понятный отказ, а не в 403 от Google.
2. **Vite dev server — часть OAuth-контура.** Redirect URI ведёт на `:5173`, и без запущенного фронта подключение аккаунта не завершится. При будущем деплое это меняется на реальный origin и требует перерегистрации URI в Google.
3. **Скомпрометированные секреты.** `VITE_YOUTUBE_CLIENT_SECRET` уезжал в бандл. Ротировать в Фазе 3 независимо ни от чего.
4. **Привязка чужого аккаунта.** `state` обязан быть привязан к `request.user` и проверяться на callback. Защита от повтора уже есть в `sessions.claim()`, привязка к пользователю — новое требование.
5. **Потеря `TOKEN_ENCRYPTION_KEYS`** = все переподключают аккаунты. Хранить отдельно от файла БД.
6. **Диск.** 4 ГиБ на файл × 2 пользователя × параллельные загрузки — до ~16 ГиБ пикового занятого места до истечения 48-часового срока. Числа в константах, менять по факту.
7. **Ссылка на `File` теряется при перезагрузке** — отсюда экран переподтверждения файла. Без него четырёхгигабайтная загрузка начиналась бы заново.
8. **Возврат остальных платформ.** При порте X, Instagram и TikTok сначала починить три известных бага (опрос `STATUS` у X, опрос статуса контейнера у Instagram, фиктивный `publish()` у TikTok) и только потом переносить. Вместе с ними вернутся `ScheduledJob`, `planSchedule.ts` и режимы `stagedPublish`/`deferredUpload` — они уже написаны и лежат в `v0-desktop`.
9. **Транскодинг** PRD относил к non-goals. Полагаемся на валидацию и внятные ошибки; если YouTube начнёт отклонять файлы — отдельная задача с `ffmpeg`.
10. **Переезд на Postgres.** Заранее заложен (`DATABASE_ENGINE`, портируемое подмножество ORM, захват условным UPDATE). Триггер — `database is locked` в логах.

---

## Ключевые файлы для реализации

- `backend/multiposter/providers.py` — шов `Provider`/`PROVIDERS`, становится `PlatformProvider` + `YouTubeProvider`
- `backend/multiposter/views/common.py` — `api_response`/`guard`/`require_*`; контракт, который расширяет каждая новая ручка
- `backend/multiposter/sessions.py` — образец захвата строки условным UPDATE, единственный доступный на SQLite
- `frontend/src/services/upload/UploadManager.ts` — оркестрация, транслитерируемая в `publishing/pipeline.py`
- `frontend/src-tauri/src/commands/youtube_upload.rs` — спецификация resumable-загрузки и общего retry-каркаса
- `frontend/src/platforms/youtube/YouTubeAuth.ts` — логика PKCE, refresh и `getValidAccessToken`, уезжающая в `platforms/youtube/oauth.py`
- `.claude/CLAUDE.md` — операционное руководство, которое теперь по большей части перевёрнуто
