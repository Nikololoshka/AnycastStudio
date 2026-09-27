# TikTok: перенос из v0-desktop в web

## Context

Публикация на YouTube работает. Следующая платформа — TikTok. Реализация desktop-клиента (Tauri) лежит в теге
`v0-desktop` (`frontend/src/platforms/tiktok/*`, `src-tauri/src/commands/tiktok_upload.rs`) и по ADR 0001 служит
спецификацией для порта на Python. Попутно чиним известные дефекты desktop: `publish()` всегда возвращал успех,
`state` не проверялся, секреты лежали в бандле, privacy был жёстко `SELF_ONLY`.

Цель — TikTok Direct Post (`video.publish`, `FILE_UPLOAD`) с UI, пригодным для аудита TikTok, отложенной публикацией
через beat и подтверждением публикации опросом статуса.

## Принятые решения

| # | Решение |
|---|---|
| 1 | Приложение в TikTok Developer — тип **Desktop**, redirect `http://localhost:5173/api/social/tiktok/callback` |
| 2 | UI сразу под аудит TikTok |
| 3 | `scheduling: "deferredUpload"`, beat раз в минуту ставит в работу target с наступившим `publish_at` |
| 4 | Реестр publisher в `publishing/publishers/`, `pipeline.py` общий |
| 5 | После upload → `processing` + задача `publishing.poll_target` с countdown 10/30/60/120 с, таймаут 30 мин → `failed` (PLATFORM, «не подтверждено, проверь вручную»), без автоповтора |
| 6 | Аренда refresh-токена через условный UPDATE |
| 7 | Caption = `title + "\n\n" + description + " #hashtags"`, ≤ 2200 UTF-16 |
| 8 | `PlatformProvider.code_challenge(verifier)`; TikTok — hex SHA-256 |
| 9 | `GET /api/social/accounts/<id>/creator-info`, кеш Redis 5 мин, 404 на чужой/не-TikTok аккаунт; worker перепроверяет перед init |
| 10 | Панель: privacy без дефолта, флаги с блокировкой по creator_info, раскрытие коммерческого контента (organic/branded, branded ≠ SELF_ONLY), isAigc, cover frame, текст согласия |
| 11 | Только Direct Post |
| 12 | Resume через `{publish_id, upload_url, chunk_size, next_chunk, expires_at}`; истёк — новый init; чанк `PLATFORM_CHUNK_BYTES` |
| 13 | Шесть коммитов, каждый после проверки пользователем |

## Шаги (по коммитам)

### 1. Реестр publisher (рефакторинг без изменения поведения)
- `backend/publishing/publishers/{__init__,youtube}.py`: интерфейс `validate(target, asset) -> ValidationResult`,
  `upload(target, asset, token, resume, on_progress, should_cancel) -> UploadOutcome`, `publish(...)`,
  исключение `NeedsFreshToken`/`Cancelled` в общем виде. Реестр `PUBLISHERS = {"youtube": ...}`.
- Из `pipeline.py` в `publishers/youtube.py` переезжают `_validate`, `_privacy_at_upload`, `_metadata`,
  YouTube-часть `_upload` / `_publish`, проверка `youtube.NeedsFreshToken` в `_error_of`.
- `pipeline.run_target` остаётся: claim → cancel check → validate → upload → publish; `_set`, `_progress_recorder`,
  refresh-once-on-401 — общие.
- Проверка: существующие `publishing/tests/*` зелёные без правок.

### 2. Отложенный запуск (`deferredUpload`)
- `publishing/services.dispatch`: для платформы с `scheduling == "deferredUpload"` и `publish_at` в будущем — не
  ставить задачу сразу.
- Beat-задача `publishing.dispatch_due_targets` (раз в 60 с) в `config/settings/base.py`: queued target с
  `publish_at <= now` → `run_target.delay`; claim в pipeline гарантирует единственный запуск.
- Та же задача подбирает `processing` target, у которых `last_activity_at` старше порога (потерянная цепочка опроса),
  и ставит `poll_target`.
- Тесты: не запускается раньше срока; запускается после; двойной dispatch не даёт двух прогонов.

### 3. Аренда refresh-токена (`backend/social/`)
- Поле `SocialAccount.refresh_lease_until` + миграция.
- `services.refresh_access_token`: условный UPDATE захватывает аренду; проигравший ждёт/перечитывает запись и берёт
  уже обновлённый токен. Сетевой вызов — вне транзакции.
- Тесты: два конкурентных refresh → один запрос к платформе, аккаунт не уходит в `needs_reauth`.

### 4. PKCE через provider
- `platforms/oauth/provider.py`: `code_challenge(verifier) -> str` в протоколе.
- `YouTubeProvider.code_challenge` → `pkce.s256_challenge`.
- `social/sessions.create(user, provider)` вызывает `provider.code_challenge` при `uses_pkce`.
- Тесты social остаются зелёными.

### 5. Backend TikTok
- `backend/platforms/tiktok/`:
  - `oauth.py` — `TikTokProvider`: `client_key`, authorize `https://www.tiktok.com/v2/auth/authorize/`, token/refresh
    `https://open.tiktokapis.com/v2/oauth/token/` (form, с `client_secret`), revoke, identity из
    `/v2/user/info/?fields=open_id,display_name,avatar_url`; scopes `user.info.basic,video.publish`; hex PKCE;
    `redirect_uri` через `PUBLIC_ORIGIN` + `reverse('social-callback')`.
  - `envelope.py` — проверка `{"error":{"code","message","log_id"}}` в 200-ответах поверх `http.classify`.
  - `creator_info.py` — `query(token) -> CreatorInfo`.
  - `upload.py` — init `/v2/post/publish/video/init/` (post_info + source_info FILE_UPLOAD), PUT чанков с
    `Content-Range`, финальный 201, `ResumeState` как в решении 12, `NeedsFreshToken` на 401, через `http.with_retry`.
  - `status.py` — `/v2/post/publish/status/fetch/`; `PUBLISH_COMPLETE` → успех (URL из
    `publicaly_available_post_id`, если есть), `FAILED` → `PlatformFailure` по `fail_reason` (таблица из desktop).
  - `video_options.py` — `VideoOptions` (privacyLevel=None, disable*, brandOrganic, brandContent, isAigc,
    coverFrameSeconds), `video_options_of`, `caption_of(title, description, hashtags)`, `MAX_CAPTION_LENGTH=2200`.
  - `capabilities.py` — label TikTok, `deferredUpload`, title/description/hashtags, 4 GiB, mp4/quicktime/webm;
    `validate` (размер, тип, длина caption, privacy выбран, branded ≠ SELF_ONLY).
- `publishing/publishers/tiktok.py`: validate + creator_info-проверка (privacy в опциях, длительность ≤ max,
  OR флагов disable), upload, publish = переход в `processing` и постановка `poll_target`.
- `publishing/tasks.py`: `publishing.poll_target` — claim по статусу `processing`, опрос, перепланирование по
  графику, таймаут 30 мин. Отмена после upload невозможна — `cancel_requested` игнорируется с понятным сообщением.
- Регистрация: `social/providers.py`, `publishing/views/platforms.py`, `publishing/publishers/__init__.py`.
- `social/views/creator_info.py` + url; `@require_auth`, `@rate_limit`, фильтр по `request.user`, кеш.
- Settings: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` (base, test), блок в `.env.example`.
- Тесты (`PlatformTestCase`, мок `platforms.http.transport.requests.request`): OAuth (hex challenge, envelope-ошибка,
  refresh с ротацией), upload offsets/Content-Range/финальный 201/resume/истёкший upload_url, каждый `fail_reason`,
  poll до успеха/таймаута, creator_info endpoint (чужой аккаунт → 404, не-TikTok → 404, кеш), контракт дефолтов
  TS↔Python для TikTok.

### 6. Frontend TikTok
- `domain/platform/order.ts`: `AVAILABLE_PLATFORMS = ['youtube', 'tiktok']`.
- `platforms/tiktok/{settings.ts, TikTokDescriptor.ts, TikTokSettingsPanel.tsx, index.ts}` по образцу youtube;
  `TIKTOK_DEFAULT_SETTINGS` для контракт-теста.
- Регистрация в `platforms/registry.ts`, `platforms/settings.ts`, `features/composer/PlatformTab.tsx`.
- `api/accountsApi.ts`: `getCreatorInfo(accountId)`.
- Панель на HeroUI: ник автора, privacy select без дефолта, заблокированные флаги, раскрытие коммерческого контента,
  isAigc, cover frame, текст согласия; блокировка публикации, пока privacy не выбран.
- Composer: подсказка для `deferredUpload`; `summary.needsAccount` без хардкода «YouTube».
- Локали `en`/`ru` синхронно (`platforms.json`, `composer.json`); убрать sandbox-предупреждение.
- Vitest: `caption`/длина UTF-16, нормализация настроек.

### Документация
- `docs/platforms/tiktok.md` (регистрация Desktop-приложения, redirect, аудит, лимиты), README, CLAUDE.md
  («YouTube only» → YouTube + TikTok), `docs/architecture.md`.

## Действия пользователя
- Создать новую пару client key/secret (старая из desktop-бандла скомпрометирована), тип Desktop, redirect из решения 1,
  продукты Login Kit + Content Posting API (Direct Post), scopes `user.info.basic`, `video.publish`.

## Verification
- `.venv/Scripts/python manage.py test --settings=config.settings.test` после каждого коммита.
- `npx tsc --noEmit`, `npm run lint`, `npm test`.
- Вручную: подключить TikTok-аккаунт через `localhost:5173`, проверить creator-info в панели, опубликовать
  короткое видео (SELF_ONLY до аудита), увидеть `processing` → `completed`; отложенная публикация на +2 мин;
  убить worker посреди загрузки и убедиться, что загрузка продолжилась.
