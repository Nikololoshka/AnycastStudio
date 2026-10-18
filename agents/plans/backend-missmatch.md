# Бэкенд под новый дизайн: чего не хватает

## Context

Фронтенд переведён на новый дизайн (коммиты 1b42181…0193022). Всё, чего не было на
сервере, замокано на клиенте. Этот план — что добавить в Django-бэкенд, чтобы убрать
моки, и что сознательно оставить без бэкенда.

Найдено при разборе:
- `User` уже хранит `locale`, `timezone`, `theme` и отдаёт их в `/api/auth/me`
  (`accounts/views/serializers.py::user_json`). Язык, тема и часовой пояс — локальные
  настройки браузера: SPA держит их в `localStorage`, на сервер они не пишутся.
- Черновики живут только в `localStorage` (`frontend/src/api/draftsApi.ts`). При этом
  сервер сам удаляет файлы, на которые нет публикаций, через `ORPHAN_ASSET_TTL_HOURS = 48`
  (`media/services.py::never_published_since`). **Видео черновика пропадает через двое
  суток** — это баг, а не просто отсутствующая фича.
- Автоочистка уже есть и глобальная: `MEDIA_RETENTION_HOURS = 48` после публикации
  (`media/services.py::unused_assets`, команда `sweep_media`, Celery beat). Настройка
  автоочистки в UI — мок в `profileApi.ts`.
- Удаление публикации — мок: скрытие id в `localStorage` (`publicationsApi.ts`).
- Настройки платформ по умолчанию (какие платформы выбирать в новой публикации и их
  настройки) — мок в `localStorage` (`frontend/src/api/platformDefaultsApi.ts`, ключи
  `defaultPlatforms`, `platformSettings`). Composer подхватывает новые значения через
  matcher на `updatePlatformDefaults.matchFulfilled` в `composerSlice.ts`, если
  публикация ещё не тронута.
- В composer есть флаг `dirty` («несохранённые изменения»). Он только клиентский и
  исключён из `DraftContent` (`draftsApi.ts`); сбрасывается через `draftSaved` после
  каждого сохранения черновика.
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
- Схема черновика повторяет `DraftContent` без `draftId` и `dirty`; `dirty` на сервер
  не уходит. После ответа сервера по-прежнему `dispatch(draftSaved(draft.id))` — это
  снимает индикатор несохранённых изменений.
- Фронтенд: `draftsApi.ts` с `queryFn` → обычные `query` к API; одноразовый перенос
  старых черновиков из `localStorage` (POST каждого, потом очистка ключа).
- Тесты: CRUD, изоляция пользователей (404), sweep не трогает ассет черновика.

### 2. Настройки пользователя: автоочистка и платформы по умолчанию — P1
- `PATCH /api/auth/me` в `accounts/views/auth.py` принимает только
  `media_retention_hours` и настройки платформ по умолчанию. Язык, тема и часовой пояс
  остаются в `localStorage` и через API не меняются.
- `User.media_retention_hours = PositiveIntegerField(null=True, default=48)`, выбор
  168/720/2160 или «не удалять» = null; миграция. `published_and_done_since` считает
  срок по пользователю вместо глобальной `MEDIA_RETENTION_HOURS` (её оставить как
  значение по умолчанию поля).
- Настройки платформ по умолчанию: `User.default_platforms` (JSON, список из
  `AVAILABLE_PLATFORMS`) и `User.platform_defaults` (JSON, по платформе). Отдаются в
  `/me`, пишутся тем же `PATCH`. Каждая платформа проверяется своей схемой опций
  (`platforms/*/publish/*_options.py`), неизвестные платформы и ключи → `invalid`.
- Фронтенд: автоочистка берётся из `/me` и пишется через PATCH, её мок из
  `api/profileApi.ts` убрать; `timeZone` в `profileApi.ts` остаётся локальным.
- Фронтенд: `platformDefaultsApi.ts` с `queryFn` → запросы к API. Имя и форму мутации
  `updatePlatformDefaults` (`{ selected, settings }`) сохранить, иначе отвалится
  matcher в `composerSlice.ts`. Перенос значений из `localStorage` — как у черновиков.
- Тесты: enum автоочистки, sweep с персональным сроком, отказ на неизвестную платформу
  и неверные опции в настройках по умолчанию.

### 3. Удаление публикации — P1
- `DELETE /api/publications/<id>`: разрешено, только если нет активных целей
  (`PublicationTarget.ACTIVE`), иначе 409. Мягкое удаление: `Publication.hidden_at`
  (видео на платформах не трогаем, история публикации для ассета сохраняется, `PROTECT`
  на ассете не мешает). Список и detail фильтруют `hidden_at__isnull=True`.
- Фронтенд: убрать `deletedPublicationIds` из `publicationsApi.ts`. В списке
  публикаций клик по строке открывает `/publications/<id>`, попапа «Ссылки» больше нет:
  ссылки на платформы смотрят на странице публикации, отдельного API не нужно.
- Тесты: 404 чужая, 409 активная, исчезает из списка.

### 4. Превью видео — P3
- Браузер уже делает кадр (`VideoFile.thumbnailDataUrl`). Отправлять его JPEG вместе с
  `uploads/<id>/complete` (до 200 КБ, проверка сигнатуры JPEG), хранить рядом с файлом,
  отдавать `GET /api/media/assets/<id>/thumbnail` с проверкой владельца.
  `asset_json` получает `thumbnailUrl`. Без ffmpeg — новой зависимости не нужно.
- Удаление ассета удаляет и превью.

## Что НЕ делаем на бэкенде

- **Язык, тема, часовой пояс** — локальные настройки браузера, остаются в
  `localStorage`. Поля `User.locale/timezone/theme` на сервере не используются.
- **Сессии и смена пароля** — в UI их нет; пароль меняет админ.
- **Уведомления в приложении** — пока не нужны.
- **Обложка в composer** — фронтенд: выбранный кадр пишется в `coverFrameSeconds`
  TikTok/Instagram. Своя картинка для YouTube требует загрузки thumbnail через API
  канала — отдельная задача, когда понадобится.
- **Поиск в шапке, сводка «Обзора», категории медиатеки, пагинация** — данных мало,
  клиент считает сам. Серверная пагинация — когда публикаций станут сотни.
- **Согласие с правилами TikTok** — только текст в карточке «Время публикации»
  (`platforms/tiktok/TikTokConsent.tsx`); бэкенд согласие не хранит.
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
- `frontend/src/api/{draftsApi,profileApi,publicationsApi,authApi,platformDefaultsApi}.ts`
- `frontend/src/features/composer/composerSlice.ts` (флаг `dirty`, matcher на
  `updatePlatformDefaults`)

## Проверка

Из `backend/`:

```sh
.venv/Scripts/python manage.py makemigrations
.venv/Scripts/python manage.py test --settings=config.settings.test
```

Из `frontend/`: `npx tsc --noEmit && npm run lint && npm test`.

Вручную: сохранить черновик с видео, прогнать `manage.py sweep_media` с подставленным
временем — видео черновика остаётся; сменить автоочистку и платформы по умолчанию —
переживает перелогин и другой браузер; после смены платформ по умолчанию нетронутая
«Новая публикация» показывает новые значения, а начатая — свои; сохранение черновика
снимает точку «несохранённые изменения»; удалить завершённую публикацию.
