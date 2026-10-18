# Бэкенд под новый дизайн: план реализации

## Context

Фронтенд переведён на новый дизайн, всё, чего нет на сервере, замокано в `localStorage`
(`agents/plans/backend-missmatch.md`). Главный баг: черновики живут только в браузере, а
`media/services.py::never_published_since` удаляет их видео через 48 ч. Цель — перенести на
сервер черновики, автоочистку, платформы по умолчанию, удаление публикации и превью.

Решения (3 раунда вопросов):
- Draft — отдельные колонки, id = int pk, видео — только `asset` FK (недогруженное видео
  в черновик не попадает).
- Автоочистка — `User.media_retention_days`: 7/30/90 или `null` = не удалять, по умолчанию 30.
- Настройки платформ в defaults и черновиках проверяются строго через существующие `*Options`
  (round-trip); `CreatePublicationSchema` не трогаем.
- Удаление публикации — мягкое, `hidden_at`.
- Старые данные из `localStorage` не переносим, ключи удаляем.
- Черновики в `publishing/`, ORM прямо во views (как `media/views/assets.py`), без use case.
- Превью — включено, последним коммитом.

Стиль URL как в проекте: один URL на одно действие, метод через `require_*`.

## Коммит 0 (часть коммита 1): строгая проверка настроек платформ

`platforms/platform_catalog.py::PlatformCatalog` — два classmethod рядом с
`capabilities_by_platform`, словарь `{PlatformType: Options}` для четырёх `*Options`:
- `normalized_settings(platform, raw) -> dict` = `Options.of(raw).as_json()`;
- `is_exact_settings(platform, raw) -> bool` = `normalized_settings(p, raw) == {**normalized_settings(p, {}), **raw}`.
  Лишний ключ, неверный тип или значение → `False`.

Pydantic `field_validator` в каждой схеме (черновик, preferences) вызывает
`is_exact_settings` для каждой платформы и выдаёт `ValueError(f"invalid settings for {platform}")`;
`validate` превращает это в `400 invalid`. Ключи словаря типизированы `PlatformType`, поэтому
неизвестная платформа отклоняется сама.

## 1. Черновики на сервере — P1

Бэкенд:
- `publishing/models.py::Draft`: `user` FK CASCADE, `asset` FK `media.MediaAsset` SET_NULL null,
  `title` CharField(300, blank), `description` TextField(blank), `hashtags` JSON list,
  `publish_at` null, `selected_platforms` JSON list, `platform_settings` JSON dict,
  `created_at`, `updated_at` auto_now. `__str__` → title или `draft <pk>`. Миграция.
- `publishing/views/schemas.py::DraftSchema`: `mediaAssetId: int | None`, `title` ≤300,
  `description` ≤10 000, `hashtags` ≤60, `publishAt: AwareDatetime | None`,
  `selectedPlatforms: list[PlatformType]` без повторов, `platformSettings: dict[PlatformType, dict]`
  со строгой проверкой.
- `publishing/views/serializers.py::draft_json`: `id`, `video` = `asset_json(draft.asset)` из
  `media/views/serializers.py`, если ассет есть и `READY`, иначе `null`; остальные поля
  в camelCase; `updatedAt`.
- `publishing/views/drafts.py` (по образцу `publications.py`, `_owned_drafts(user)`):
  - `GET  /api/drafts` → `publishing_list_drafts`, `-updated_at`;
  - `POST /api/drafts/create` → `publishing_create_draft`;
  - `GET  /api/drafts/<pk>` → `publishing_get_draft`;
  - `POST /api/drafts/<pk>/update` → `publishing_update_draft` (полная замена);
  - `DELETE /api/drafts/<pk>/delete` → `publishing_delete_draft`.
  Чужой → 404. `mediaAssetId` не своего или не `READY` ассета → `invalid` с полем `mediaAssetId`.
- `media/services.py`: `never_published_since` добавляет `drafts__isnull=True`; `is_in_use`
  возвращает `True` и при наличии черновика → удаление ассета из медиатеки даёт 409 `asset_in_use`.
- Admin: зарегистрировать `Draft` в `publishing/admin.py` (поля без токенов, ничего чувствительного).

Фронтенд:
- `api/draftsApi.ts`: `queryFn` → обычные `query` на эти URL, `id: number`, `video` из ответа
  сервера маппится в `VideoFile` (`mediaAssetId`, имя, размер, длительность). Отправляется
  `mediaAssetId`, а не `video`. Ключ `drafts` убрать из `STORAGE_KEYS`.
- `composerSlice.ts`: `draftId?: number`; `draftSaved(draft.id)` после ответа как сейчас.
- Роут `/compose/:id` парсит число.

Тесты `publishing/tests/test_drafts.py`: CRUD; чужой черновик → 404 на get/update/delete;
неизвестная платформа и лишний ключ в `platformSettings` → 400; чужой ассет → 400.
`media/tests/test_sweeps.py`: старый ассет с черновиком переживает sweep; после удаления
черновика — удаляется. `media/tests/test_assets.py`: удаление ассета черновика → 409.

## 2. Автоочистка и платформы по умолчанию — P1

Бэкенд:
- `config/settings/base.py`: `MEDIA_RETENTION_HOURS = 48` → `MEDIA_RETENTION_DAYS = 30`.
- `accounts/models.py::User`:
  - `media_retention_days = PositiveSmallIntegerField(null=True, blank=True, default=settings.MEDIA_RETENTION_DAYS, choices=[(7, …), (30, …), (90, …)])`;
  - `default_platforms = JSONField(null=True, blank=True)` — `null` = все платформы;
  - `platform_defaults = JSONField(default=dict, blank=True)`.
  Миграция.
- `media/services.py::unused_assets`: вместо глобального срока — для каждого из 7/30/90
  `published_and_done_since(now - timedelta(days=d)).filter(user__media_retention_days=d)`;
  `null` не попадает ни в один. `ORPHAN_ASSET_TTL_HOURS` не меняется.
- `accounts/views/serializers.py::user_json` + `mediaRetentionDays`, `defaultPlatforms`
  (`null` → все `PlatformType` по порядку), `platformDefaults` — для каждой платформы
  `PlatformCatalog.normalized_settings(p, saved.get(p, {}))`.
- `accounts/views/schemas.py::PreferencesSchema`: все поля необязательны —
  `mediaRetentionDays: Literal[7, 30, 90] | None`, `defaultPlatforms: list[PlatformType]`,
  `platformDefaults: dict[PlatformType, dict]` со строгой проверкой.
- `accounts/views/auth.py::account_update_preferences`, `PATCH /api/auth/me/preferences`:
  пишет только поля из `data.model_fields_set`, `save(update_fields=…)`, отвечает
  `user=user_json(user)`. `locale/timezone/theme` через API не меняются.

Фронтенд:
- `api/profileApi.ts`: `autoDeleteSources` берётся из `/me` (`enabled = days !== null`) и пишется
  PATCH; `timeZone` остаётся локальным.
- `api/platformDefaultsApi.ts`: query/mutation к `/me` и `/me/preferences`; имя
  `updatePlatformDefaults` и форма `{ selected, settings }` сохраняются (matcher в
  `composerSlice.ts`). `readPlatformDefaults()` в `initialComposer` → значения из встроенных
  `*_DEFAULT_SETTINGS`, пока `/me` не загружен. Ключи `defaultPlatforms`, `platformSettings`,
  `profilePreferences` убрать.

Тесты `accounts/tests/test_preferences.py`: PATCH каждого поля; недопустимое значение
автоочистки (48) → 400; неизвестная платформа и неверная опция → 400; без входа → 401;
`/me` отдаёт нормализованные defaults нового пользователя. `media/tests/test_sweeps.py`:
пользователь на 7 днях теряет файл через 8 дней, на 90 — нет, `null` — никогда.
Существующие тесты с `MEDIA_RETENTION_HOURS` переписать.

## 3. Удаление публикации — P1

Бэкенд:
- `Publication.hidden_at = DateTimeField(null=True, blank=True)`, миграция.
- `publishing/views/publications.py`: `_owned_publications` добавляет `hidden_at__isnull=True`,
  этим закрываются list, detail, ответы cancel/retry.
- `publishing_delete_publication`, `DELETE /api/publications/<pk>/delete`: условный UPDATE
  `filter(user, pk, hidden_at__isnull=True).exclude(targets__status__in=PublicationTarget.ACTIVE).update(hidden_at=now)`;
  0 строк → 404, если публикации нет, иначе 409 `conflict`, `message="publication_active"`.
- `publishing/repositories/target_repository.py`: поиск цели для cancel/retry исключает
  скрытые публикации (`publication__hidden_at__isnull=True`), иначе retry оживит скрытую.
- Дневной лимит считает и скрытые — удаление его не обходит.

Фронтенд: убрать `deletedPublicationIds` и ключ `deletedPublications` из `publicationsApi.ts`,
`deletePublication` → `DELETE` запрос.

Тесты `publishing/tests/test_delete.py`: чужая → 404; активная → 409; завершённая исчезает
из list и detail; retry цели скрытой → 404.

## 4. Превью видео — P3

Бэкенд:
- `CompleteUploadSchema.thumbnailJpeg: str | None` — base64 без префикса data URL;
  после декодирования ≤200 КБ и начинается с `FF D8 FF`, иначе `invalid`.
- `MediaAsset.thumbnail_path = CharField(max_length=500, blank=True)`, миграция.
- `media/storage.py::thumbnail_path(user_id, asset_id)` → `<user>/<asset>/thumbnail.jpg`,
  `write_bytes`. `services.complete` пишет файл и путь.
- `services.delete_asset` удаляет и превью, обнуляет `thumbnail_path`.
- `GET /api/media/assets/<pk>/thumbnail` → `media_asset_thumbnail`: `FileResponse`
  `image/jpeg` для своего `READY` ассета с превью, иначе 404.
- `asset_json` + `thumbnailUrl` (или `null`) → попадает и в `draft_json.video`.

Фронтенд: `uploadClient` отправляет `thumbnailDataUrl` без префикса в `complete`; `VideoFile`
из черновика берёт `thumbnailUrl`.

Тесты `media/tests/test_complete.py`: валидный JPEG сохраняется и отдаётся владельцу;
чужой → 404; PNG и >200 КБ → 400; удаление ассета удаляет превью. Диск — как в
существующих тестах `media/tests/base.py`.

## Не делаем

Язык/тема/часовой пояс (браузер), сессии и смена пароля, уведомления, своя обложка YouTube,
серверный поиск/пагинация, хранение согласия TikTok, «Увеличить место», удаление аккаунта,
правка запланированной публикации — как в `backend-missmatch.md`.

## Критичные файлы

- `backend/platforms/platform_catalog.py`
- `backend/publishing/{models.py,urls.py,admin.py,views/{drafts,publications,schemas,serializers,__init__}.py,repositories/target_repository.py}`
- `backend/media/{models.py,services.py,storage.py,urls.py,views/{assets,uploads,schemas,serializers}.py}`
- `backend/accounts/{models.py,urls.py,views/{auth,schemas,serializers,__init__}.py}`
- `backend/config/settings/base.py`
- `frontend/src/api/{draftsApi,profileApi,publicationsApi,platformDefaultsApi}.ts`,
  `frontend/src/features/composer/composerSlice.ts`, `frontend/src/services/storage/localSettings.ts`

## Проверка

```sh
cd backend
.venv/Scripts/python manage.py makemigrations
.venv/Scripts/python manage.py test --settings=config.settings.test
cd ../frontend
npx tsc --noEmit && npm run lint && npm test
```

Вручную: сохранить черновик с загруженным видео, подменить `created_at` ассета на −3 дня,
`manage.py sweep_media` — файл на месте; удалить черновик, sweep — файл удалён. Сменить
автоочистку и платформы по умолчанию — переживает перелогин и другой браузер; нетронутая
«Новая публикация» подхватывает новые defaults. Удалить завершённую публикацию, попытаться
удалить активную — 409. Превью видно в открытом черновике после перезагрузки.
