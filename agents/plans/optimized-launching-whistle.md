# Веб-раскладка фронтенда: фиксированный appbar, сайдбар публикаций, страница файлов

## Context

Фронтенд остался с раскладки десктоп-приложения (Tauri): узкая колонка `max-w-6xl`,
шапка прокручивается вместе со страницей, публикации — отдельная страница карточек.
Нужен полноэкранный веб-интерфейс: шапка зафиксирована, слева постоянный список
публикаций (опубликованные + черновики) с созданием/удалением и счётчиком места
на сервере, отдельная страница загруженных файлов. Только фронт; чего нет на
сервере — мок.

Что уже есть на сервере (используем по-настоящему, без мока):
- `GET /api/media/assets` → `{assets, usedBytes, quotaBytes}` (`backend/media/views/assets.py`)
- `DELETE /api/media/assets/<id>` → `ok` / `conflict` с `message: "asset_in_use"`
- `GET /api/publications` — уже есть `useGetPublicationsQuery`

Чего нет (мок): черновики (CRUD) и удаление публикации.

## Раскладка

```
┌──────────── AppTopBar (полная ширина, не скроллится) ────────────┐
│ лого · Создать · Файлы · Аккаунты          язык · тема · выход  │
├───────────────┬──────────────────────────────────────────────────┤
│ + Новая       │                                                  │
│ ─────────     │   <Outlet/> — свой скролл, на всю ширину          │
│ список        │                                                  │
│ (свой скролл) │                                                  │
│ ─────────     │                                                  │
│ 1.2/5 ГБ ▓▓░░ │                                                  │
└───────────────┴──────────────────────────────────────────────────┘
```

- `components/AppShell/AppShell.tsx`: `h-dvh flex flex-col overflow-hidden`;
  под шапкой `flex flex-1 min-h-0` = `<PublicationsSidebar/>` (`w-80`, `border-r`,
  `hidden lg:flex`) + `<main className="flex-1 overflow-y-auto">`. Шапка
  фиксирована естественно — скроллится только `main`; убрать `max-w-6xl`.
- `AppTopBar.tsx`: убрать `max-w-6xl`/`mx-auto`, добавить `border-b bg-surface`.
  `NAV_ITEMS`: `/compose`, `/files`, `/settings/accounts` (Публикации уходят из меню).
- `styles.css`: убрать десктопный `user-select: none` с `body`.

## Данные (`src/api/`)

- **`mediaApi.ts`** (реальный): `getMediaAssets` → `{assets: MediaAsset[], usedBytes, quotaBytes}`,
  `providesTags: ['MediaAsset']`; `deleteMediaAsset(id)` (DELETE),
  `invalidatesTags: ['MediaAsset']`. Экспорт из `api/index.ts`.
- **`draftsApi.ts`** (мок, весь файл заменится на `query` при появлении бэкенда):
  эндпоинты через `queryFn` над массивом в `localStorage` (через существующий
  `services/storage` `readStored` + ключ в `STORAGE_KEYS`): `getDrafts`,
  `getDraft(id)`, `saveDraft` (create/update по наличию `id`), `deleteDraft`.
  Тег `'Draft'` добавить в `baseApi.tagTypes`. Тип `Draft` = поля `ComposerState`
  без `video` + `mediaAssetId?`, `filename?`, `id`, `updatedAt`.
- **Удаление публикации (мок)**: `deletePublication` в `publicationsApi.ts` через
  `queryFn`, который кладёт id в скрытый набор в `draftsApi.ts`-модуле; `getPublications`
  отфильтровывает эти id в `transformResponse`. `invalidatesTags: ['Publication']`.

## Сайдбар — `features/publications/PublicationsSidebar.tsx`

- Сверху кнопка «Новая публикация» → `dispatch(composerReset())`, `navigate('/compose')`.
- Список: черновики + публикации, слитые и отсортированные по дате (новые сверху).
  Элемент — `NavLink`: заголовок (или «Без названия»), дата, `PlatformGlyph` целей,
  `Chip` статуса («Черновик» / статус публикации; активные — пульс `lamp-pulse`).
  Черновик → `/compose/:draftId`, публикация → `/publications/:id`.
- Удаление: иконка `Trash2` на элементе → подтверждение HeroUI-модалкой
  (`AlertDialog`, если есть в `@heroui/react` 3.2, иначе `Modal`) → `deleteDraft` /
  `deletePublication`; если удалён открытый элемент — `navigate('/compose')`.
- Поллинг как сейчас в `PublicationsScreen`: `ACTIVE_POLL_MS`, `skipPollingIfUnfocused`.
- Снизу `StorageMeter` (тот же файл): `useGetMediaAssetsQuery` → HeroUI `ProgressBar`/`Meter`
  + «1,2 ГБ из 5 ГБ». Байты форматировать `Intl.NumberFormat(lang, {style:'unit', unit:'gigabyte'|'megabyte'})`
  локальной функцией внутри файла (без shared utils).

## Страница файлов — `features/media/FilesScreen.tsx` (новая фича)

- Маршрут `/files`. Таблица HeroUI `Table`: имя, размер, длительность,
  разрешение, дата, кнопка удаления с подтверждением. Ответ `conflict`
  (`asset_in_use`) → сообщение «Файл используется в публикации».
- Пустое состояние — как сейчас в `PublicationsScreen` (`Inbox` + текст).
- `features/media/index.ts` экспортирует экран.

## Редактор и черновики

- `router/index.tsx`: `compose` и `compose/:draftId` → `ComposerScreen`;
  `files` → `FilesScreen`; `publications` (без id) → `<Navigate to="/compose">`;
  `publications/:id` остаётся.
- `composerSlice.ts`: `composerReset` (вернуть `initialComposer()`) и
  `draftLoaded(draft)` (заполнить поля; `video` собрать из `mediaAssetId`/`filename`).
- `ComposerScreen.tsx`: при `:draftId` — `useGetDraftQuery` → `draftLoaded`;
  убрать `pt-6`-обёртку под новую раскладку (`p-6`, без фиксированной ширины формы
  кроме правой колонки `SummaryPanel`).
- `SummaryPanel.tsx`: кнопка «Сохранить черновик» (`saveDraft`, после create —
  `navigate('/compose/:id')`); после успешной публикации из черновика — `deleteDraft`.
- Удалить `PublicationsScreen.tsx` (сайдбар его заменяет), `PublicationScreen.tsx`
  растянуть на ширину (`Card` без `mt-6`, отступ даёт `main`).

## Локализация

`en` и `ru` синхронно: `common.json` → `nav.files`, `sidebar.*` (new, draft,
untitled, delete, confirm, storage); новый неймспейс `media.json` (экран файлов),
зарегистрировать в `app/i18n/resources.ts`; `composer.json` → `summary.saveDraft`.

## Пропущено осознанно

- Мобильный drawer для сайдбара (на `< lg` сайдбар скрыт) — добавить, когда понадобится мобильный.
- Выбор уже загруженного файла в редакторе со страницы файлов — не просили.
- Удаление Tauri-зависимостей из `package.json` — отдельная задача.

## Проверка

Из `frontend/`:
```bash
npx tsc --noEmit && npm run lint && npm test
```
Вручную (`npm run dev` + бэкенд): шапка не двигается при прокрутке длинного
редактора; сайдбар и `main` скроллятся независимо; создать черновик → появился в
списке, открыть, изменить, сохранить, перезагрузить страницу → на месте; удалить
черновик и публикацию с подтверждением; `/files` показывает реальные файлы,
удаление обновляет счётчик места; переключить язык en/ru — нет сырых ключей;
светлая/тёмная темы.
