# Бэкенд под новый дизайн: чего не хватает

## Context

Фронтенд переведён на новый дизайн (коммиты 1b42181…0193022). Всё, чего не было на
сервере, замокано на клиенте. Этот план — что добавить в Django-бэкенд, чтобы убрать
моки, и что сознательно оставить без бэкенда.

Найдено при разборе:
- `User` уже хранит `locale`, `timezone`, `theme` и отдаёт их в `/api/auth/me`
  (`accounts/views/serializers.py::user_json`), но записать их нельзя, а SPA держит
  язык/тему только в `localStorage`.
- Черновики живут только в `localStorage` (`frontend/src/api/draftsApi.ts`). При этом
  сервер сам удаляет файлы, на которые нет публикаций, через `ORPHAN_ASSET_TTL_HOURS = 48`
  (`media/services.py::never_published_since`). **Видео черновика пропадает через двое
  суток** — это баг, а не просто отсутствующая фича.
- Автоочистка уже есть и глобальная: `MEDIA_RETENTION_HOURS = 48` после публикации
  (`media/services.py::unused_assets`, команда `sweep_media`, Celery beat).
- Удаление публикации — мок: скрытие id в `localStorage` (`publicationsApi.ts`).
- Обложка: у TikTok и Instagram уже есть `coverFrameSeconds` в настройках платформы
  (`platforms/{tiktok,instagram}/publish/*_options.py`) — бэкенд не нужен.

## Что делаем (по приоритету, каждый пункт — отдельный коммит)

### 1. Черновики на сервере — P1, чинит потерю видео
- В приложении `publishing/` модель `Draft(user FK, asset FK null
  SET_NULL, title, description, hashtags JSON, publish_at null, selected_platforms JSON,
  platform_settings JSON, created_at, updated_at)`. Миграция.
- Эндпоинты по образцу `publishing/views/publications.py` (декораторы `require_auth`,
  `validate(Schema)`, `api_response`): `GET /api/drafts`, `GET /api/drafts/<id>`,
  `POST /api/drafts` (создать), `PUT /api/drafts/<id>` (заменить), `DELETE /api/drafts/<id>`.
  Фильтр по `request.user` в queryset, чужой → 404. Pydantic-схема ограничивает размеры
  JSON.
- `media/services.py::never_published_since` и `is_in_use`: исключить ассеты, на
  которые ссылается черновик. Удаление ассета черновика → 409 `asset_in_use`, как сейчас.
- При создании публикации из черновика фронтенд и так удаляет черновик — оставить.
- Фронтенд: `draftsApi.ts` с `queryFn` → обычные `query` к API; одноразовый перенос
  старых черновиков из `localStorage` (POST каждого, потом очистка ключа).
- Тесты: CRUD, изоляция пользователей (404), sweep не трогает ассет черновика.

### 2. Настройки пользователя — P1
- `PATCH /api/auth/me` в `accounts/views/auth.py`: `locale`, `timezone` (проверка через
  `zoneinfo.available_timezones()`), `theme` (имя и почту меняет админ). Плюс новое поле `media_retention_hours` (выбор 168/720/2160 или «не удалять» = null).
- `User.media_retention_hours = PositiveIntegerField(null=True, default=48)`; миграция.
  `published_and_done_since` считает срок по пользователю вместо глобальной
  `MEDIA_RETENTION_HOURS` (её оставить как значение по умолчанию поля).
- Фронтенд: язык/тема/часовой пояс/автоочистка берутся из `/me` и пишутся через PATCH;
  `localStorage` остаётся только как кэш до логина. Мок автоочистки и часового пояса
  из `api/profileApi.ts` убрать.
- Часовой пояс сервер пока ни для чего не использует (время приходит в ISO с зоной) —
  он нужен фронтенду для отображения и подписи в DatePicker. Это нормально.
- Тесты: валидация зоны и enum, sweep с персональным сроком.

### 3. Удаление публикации — P1
- `DELETE /api/publications/<id>`: разрешено, только если нет активных целей
  (`PublicationTarget.ACTIVE`), иначе 409. Мягкое удаление: `Publication.hidden_at`
  (видео на платформах не трогаем, история публикации для ассета сохраняется, `PROTECT`
  на ассете не мешает). Список и detail фильтруют `hidden_at__isnull=True`.
- Фронтенд: убрать `deletedPublicationIds` из `publicationsApi.ts`.
- Тесты: 404 чужая, 409 активная, исчезает из списка.

### 4. Сессии и пароль — P2
- Модель `accounts.UserSession(user, session_key unique, user_agent, created_at,
  last_seen_at)`: запись создаётся в `account_login`, `last_seen_at` обновляет
  middleware не чаще раза в 5 минут (правило про троттлинг записей в SQLite).
  IP не храним.
- `GET /api/auth/sessions` (с флагом `current`), `DELETE /api/auth/sessions/<id>`:
  удаляет строку и `SessionStore(session_key).delete()` (сессии `cached_db` — удалить
  и из кэша). Текущую завершать нельзя (для этого есть logout).
- `POST /api/auth/password` (`old_password`, `new_password`, валидаторы Django,
  `rate_limit`), затем `update_session_auth_hash`; остальные сессии пользователя
  завершаются.
- Фронтенд: `getSessions`/`endSession` из `profileApi.ts` → API; включить «Сменить пароль»
  (диалог).
- Тесты: чужая сессия 404, завершённая сессия больше не авторизует, неверный старый
  пароль, rate limit.

### 5. Уведомления в приложении — P3
- Почты в проекте нет, поэтому только колокольчик. Модель `Notification(user, kind,
  publication FK null, payload JSON, created_at, read_at)`; создаётся в
  `services/usecases/publications/` через новый порт (use cases не знают Django) в
  момент, когда цель публикации завершилась или упала, и при `needs_reauth` аккаунта.
- Настройки (какие виды присылать) — JSON-поле `User.notification_prefs`, пишется тем же
  `PATCH /me`. «Еженедельная сводка на почту» и «хранилище > 90%» — убрать из UI,
  пока нет почты (или 90% считать на клиенте из `usedBytes/quotaBytes`).
- `GET /api/notifications` (последние 50), `POST /api/notifications/read`.
  Фронтенд опрашивает раз в 30–60 с — как с публикациями, без websocket.

### 6. Превью видео — P3
- Браузер уже делает кадр (`VideoFile.thumbnailDataUrl`). Отправлять его JPEG вместе с
  `uploads/<id>/complete` (до 200 КБ, проверка сигнатуры JPEG), хранить рядом с файлом,
  отдавать `GET /api/media/assets/<id>/thumbnail` с проверкой владельца.
  `asset_json` получает `thumbnailUrl`. Без ffmpeg — новой зависимости не нужно.
- Удаление ассета удаляет и превью.

## Что НЕ делаем на бэкенде

- **Обложка в composer** — фронтенд: выбранный кадр пишется в `coverFrameSeconds`
  TikTok/Instagram. Своя картинка для YouTube требует загрузки thumbnail через API
  канала — отдельная задача, когда понадобится.
- **Поиск в шапке, сводка «Обзора», категории медиатеки, пагинация** — данных мало,
  клиент считает сам. Серверная пагинация — когда публикаций станут сотни.
- **«Увеличить место»** — квоту меняет админ (`User.max_storage_bytes`); кнопку оставить
  неактивной или убрать.
- **Удаление аккаунта** — удаление пользовательских данных, по CLAUDE.md только с
  разрешения человека; аккаунты ведутся в admin. Кнопку из UI убрать или оставить
  «напишите администратору».
- **Редактирование запланированной публикации** — у YouTube видео уже загружено с
  нативным расписанием, правка требует update через API платформы для каждой из 4;
  пока достаточно «отменить и создать заново» (cancel уже есть).

## Критичные файлы

- `backend/publishing/{models.py,urls.py,views/}` (+ `views/drafts.py`, схемы, сериализатор)
- `backend/media/services.py` (sweep, `is_in_use`), `media/views/{assets,uploads}.py`
- `backend/accounts/{models.py,urls.py,views/auth.py,views/schemas.py,views/serializers.py}`
- `backend/common/responses/contract.py` — новых статусов не нужно (`conflict`,
  `not_found`, `invalid` уже есть); проверить при реализации.
- `frontend/src/api/{draftsApi,profileApi,publicationsApi,authApi}.ts`

## Проверка

Из `backend/`:

```sh
.venv/Scripts/python manage.py makemigrations
.venv/Scripts/python manage.py test --settings=config.settings.test
```

Из `frontend/`: `npx tsc --noEmit && npm run lint && npm test`.

Вручную: сохранить черновик с видео, прогнать `manage.py sweep_media` с подставленным
временем — видео черновика остаётся; сменить язык/тему/зону — переживает перелогин и
другой браузер; удалить завершённую публикацию; войти с двух браузеров и завершить одну
сессию из другой.
