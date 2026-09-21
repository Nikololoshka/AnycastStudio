# Отложенная публикация: план реализации

## Context

В composer уже есть выбор даты/времени (`ComposerCommonTab.tsx` → `setScheduledAt`), но он почти не работает:

- `scheduledAt` доходит до `UploadManager.runPublicationTask`, где единственная точка решения —
  `if (publication.scheduledAt && adapter.schedule)`;
- `schedule()` реализован **только** у YouTube (native `status.publishAt`);
- у X, Instagram, TikTok метода `schedule` нет → выбранная дата **молча игнорируется**, пост уходит
  сразу. Это самый неприятный текущий баг;
- `src/services/scheduler/index.ts` — пустая заглушка (`export {}`), никем не импортируется;
- `PlatformCapabilities.scheduling` (`'native' | 'local' | 'unsupported'`) объявлен, но не читается нигде.

Цель: довести отложенную публикацию до рабочего состояния, разведя платформы по двум разным
механизмам — серверное планирование на стороне платформы vs локальный таймер в приложении.

### Решения пользователя (зафиксировано)

- Стратегия для платформ без серверного планирования — **гибрид**: где API позволяет, медиа
  загружается заранее, в момент T делается только быстрый publish-вызов.
- Очередь задач — **только в памяти**, на диск не сохраняется.
- Трей/автозапуск — **не в этой задаче**.
- Если приложение закрыто в момент T — **ничего не делать** (задача просто исчезает вместе с сессией).

Следствие, которое надо явно показать в UI: отложенная публикация на X / Instagram / TikTok работает
только пока приложение открыто. YouTube — единственная платформа, где время сработает при закрытом
приложении (планирует сам YouTube).

---

## Матрица возможностей платформ

| Платформа | Серверное планирование | Механизм | Наш режим |
| --- | --- | --- | --- |
| **YouTube** | **Да** | `videos.insert` (private) → `videos.update` с `status.publishAt`. Требует `privacyStatus: 'private'`, иначе `publishAt` тихо игнорируется. В момент T видео становится **public**. Scope `youtube` уже запрашивается (`YouTubeAuth.ts:16-19`), так что `videos.update` доступен | `native` — загрузить сейчас, отдать дату YouTube, локальный таймер не нужен |
| **Instagram** | Нет (`scheduled_publish_time` есть только у Facebook Pages, не у IG Content Publishing) | Двухфазный: `POST /{ig-user-id}/media` создаёт контейнер (живёт **24 ч**) → `POST /{ig-user-id}/media_publish` публикует. Уже реализовано именно так: `upload()` = контейнер, `publish()` = media_publish | `stagedPublish` — контейнер заранее, `media_publish` ровно в T |
| **X** | Нет (в API v2 нет `scheduled_at`; `scheduled_tweets` есть только в Ads API) | Chunked upload → `media_id` живёт **24 ч** (`expires_after_secs: 86400`) → `POST /2/tweets`. Уже разделено так же: `upload()` = media_id, `publish()` = твит | `stagedPublish` — media_id заранее, твит ровно в T |
| **TikTok** | Нет вообще (нет server-side scheduling) | `POST /v2/post/publish/video/init/` (direct post) публикует сразу после обработки; предзагрузить и «придержать» нельзя | `deferredUpload` — загрузка стартует в T, пост появляется через несколько минут (время обработки) |

Ограничение X: аккаунт на **Free**-тарифе, `media.write` недоступен — код X не проверяем end-to-end,
тариф не меняем (см. память проекта). Планировщик для X пишем, но тестируем на YouTube/Instagram.

---

## Реализация

### 1. Расширить описание возможностей

`src/domain/platform/types.ts` — заменить строковый union на явные режимы:

```ts
export type SchedulingMode = 'native' | 'stagedPublish' | 'deferredUpload' | 'unsupported';

export interface PlatformCapabilities {
  // ...
  scheduling: SchedulingMode;
  stagedMediaTtlMs?: number; // 24 ч для instagram и x
}
```

Обновить четыре `getCapabilities()`: youtube `'native'`, instagram/x `'stagedPublish'` +
`stagedMediaTtlMs: 24 * 60 * 60 * 1000`, tiktok `'deferredUpload'`.

### 2. Чистый планировщик (домен)

Новый `src/domain/publication/planSchedule.ts` — без таймеров и Redux, чтобы легко читалось и
тестировалось:

```ts
export type ScheduledPhase = 'stage' | 'publishStaged' | 'uploadAndPublish';
export interface ScheduledJob {
  publicationId: string;
  platform: Platform;
  phase: ScheduledPhase;
  runAt: number;
}
export interface PlatformPlan {
  platform: Platform;
  immediate?: 'native' | 'stage';  // что сделать прямо сейчас, в startPublication
  jobs: ScheduledJob[];
}

export function planPublicationSchedule(
  publication: Publication,
  capabilitiesOf: (platform: Platform) => PlatformCapabilities,
  now: number,
): PlatformPlan[];
```

Правила:

- `scheduledAt` пустой или уже в прошлом → пустой план, работает текущий немедленный путь;
- `native` → `immediate: 'native'` (validate + upload + `adapter.schedule()`), задач в очереди нет;
- `stagedPublish` → `STAGE_LEAD_MS = 12ч` (половина TTL 24 ч, запас на обработку и на то, что
  приложение могло проспать тик):
  - `T - now <= STAGE_LEAD_MS` → `immediate: 'stage'` + job `publishStaged` в T;
  - иначе → job `stage` в `T - STAGE_LEAD_MS` + job `publishStaged` в T;
- `deferredUpload` → job `uploadAndPublish` в T (лид-тайм не угадываем — в UI честно пишем, что
  загрузка стартует в указанное время);
- `unsupported` → в план не попадает, платформа помечается ошибкой валидации (сейчас таких нет,
  вариант оставляем для будущих платформ).

### 3. Сервис-планировщик (таймер)

`src/services/scheduler/` (сейчас пустая заглушка):

- `SchedulerService.ts` — тик `setInterval` раз в 15 с (тик, а не `setTimeout` на будущее: устойчив к
  засыпанию машины и к длинным интервалам). Внутри: `Map<string, ScheduledJob>` с ключом
  `${publicationId}:${platform}:${phase}`, `Set` выполняющихся задач для защиты от повторного входа,
  `enqueue(jobs)`, `cancel(publicationId, platform?)`, `start(runner)`, `stop()`, `listJobs()`.
  Просроченные задачи выполняются на первом же тике (это и есть «догоняем, пока приложение живо»).
- `index.ts` — barrel.
- Логировать через `createLogger('scheduler')` (`src/services/logs`), там же уже есть редактирование
  секретов.

Раннер задач — в `src/services/upload/UploadManager.ts` (см. ниже), сервис-планировщик его только
вызывает и ничего не знает про адаптеры.

### 4. Разделить UploadManager на фазы

`src/services/upload/UploadManager.ts` — вынести из `runPublicationTask` переиспользуемые куски,
сохранив текущую сигнатуру для немедленной публикации:

- `buildAdapterPublication(publication, platformPublication, accountId)` — сборка `ctx` (сейчас inline);
- `runValidateAndUpload(...)` → `uploadedVideoId` (диспатчит `validating` / `uploading`);
- `runStage(...)` — validate + upload + `setPlatformStaged` (новый reducer, статус `'scheduled'`);
- `runPublishStaged(...)` — берёт `uploadedVideoId` из стейта, вызывает `adapter.publish`;
- `runNativeSchedule(...)` — upload + `adapter.schedule` → статус `'scheduled'`;
- `runScheduledJob(job, deps)` — единая точка входа для планировщика, свитч по `job.phase`;
- существующие `runPublicationTask` / `runPublication` остаются для «публиковать сейчас».

Ключевое: убрать `if (publication.scheduledAt && adapter.schedule)` — маршрут выбирается по
`capabilities.scheduling`, а не по наличию метода, чтобы дата больше не могла молча потеряться.

### 5. Состояние

`src/domain/publication/types.ts` — в `PlatformPublication` добавить:

```ts
uploadedVideoId?: string;  // media_id / container id / youtube video id
scheduledAt?: string;      // фактическое время публикации для этой платформы
```

`src/features/publications/publicationsSlice.ts`:

- новый reducer `setPlatformStaged({ id, platform, uploadedVideoId })` → статус `'scheduled'`,
  `progress: 100`;
- новый reducer `setPlatformScheduled({ id, platform, scheduledAt })` для «ждёт таймера»;
- `cancelPlatformSchedule({ id, platform })` → статус `'cancelled'`;
- `startPublication`: вместо безусловного `await runPublication(...)` — вызвать
  `planPublicationSchedule`, выполнить `immediate`-часть (native / stage) и передать `jobs` в
  планировщик; **не** ждать отложенные задачи;
- вынести сборку deps в `createUploadDeps(dispatch, getState)` — сейчас `getAccountId` описан inline
  внутри thunk, а планировщику нужен тот же набор.

Новый статус в `PublicationStatus` не добавляем: `'scheduled'` + наличие `uploadedVideoId` уже
различают «загружено, ждёт publish» и «ждёт загрузки».

### 6. Точка запуска

`src/app/providers/AppProviders.tsx` — новый компонент `SchedulerRunner` рядом с
`PersistedStateBootstrap`, по образцу `ThemeSync`: `useEffect` → `scheduler.start(runner)` и
`return () => scheduler.stop()`.

### 7. Исправления, всплывшие по пути (входят в задачу)

- **YouTube, окно публичности.** `upload()` отправляет `privacyStatus` из настроек (может быть
  `public`), и только потом `schedule()` понижает до `private` + `publishAt` — при отложенной
  публикации видео на несколько секунд/минут становится публичным. Фикс: при заданном `scheduledAt`
  грузить с `privacyStatus: 'private'`.
- **YouTube + non-public.** `publishAt` всегда делает видео публичным в момент T. Если выбран
  `private`/`unlisted` вместе с датой — `validate()` должен вернуть внятную ошибку (native
  scheduling несовместим с этой приватностью), а панель YouTube — показать это до нажатия кнопки.

### 8. UI и тексты

- `ComposerCommonTab.tsx`, секция `timing`: под DatePicker — список выбранных платформ с тем, как
  именно сработает время (планирует сама платформа / загрузим заранее, опубликуем в срок / загрузка
  начнётся в указанное время) и предупреждение, что для последних трёх приложение должно быть
  открыто. Режим брать через `getCapabilitiesFor` из `src/platforms/capabilities.ts` (реестр, а не
  инстанс адаптера).
- `components/UploadProgress/UploadProgress.tsx`: для статуса `'scheduled'` показывать время и,
  когда задача ждёт таймера, кнопку отмены (`cancelPlatformSchedule` + `scheduler.cancel`).
- `src/locales/{en,ru}/composer.json`: новые ключи в `timing.*` и `summary.*` (режимы, предупреждение
  про открытое приложение, «отменить», «запланировано на»). Держать `en` и `ru` синхронными — ключи
  типизированы от `en` (`src/app/i18n/i18next.d.ts`).
- `HistoryPanel` (сейчас хардкод-заглушка) и персистентная история — **вне этой задачи**.

---

## Файлы

Изменяем:

- `src/domain/platform/types.ts`, `src/domain/publication/types.ts`
- `src/platforms/{youtube,x,instagram,tiktok}/*Adapter.ts` (только `getCapabilities`, плюс у YouTube
  `upload`/`validate` по п.7)
- `src/services/upload/UploadManager.ts`
- `src/features/publications/publicationsSlice.ts`
- `src/features/composer/ComposerCommonTab.tsx`, `src/components/UploadProgress/UploadProgress.tsx`
- `src/app/providers/AppProviders.tsx`
- `src/locales/en/composer.json`, `src/locales/ru/composer.json`
- `docs/platform-publish-options.md` (обновить раздел про scheduling)

Создаём:

- `src/domain/publication/planSchedule.ts`
- `src/services/scheduler/SchedulerService.ts` (+ заполнить `index.ts`)

Переиспользуем как есть: `getCapabilitiesFor`/`getAdapterFor` (`src/platforms/capabilities.ts`),
`toPublicationError` (`src/services/upload/errors.ts`), `createLogger` (`src/services/logs`),
`buildPublicationFromComposer` (`src/domain/publication/buildPublication.ts`),
`loggingMiddleware` (логирует новые экшены автоматически).

---

## Проверка

1. `npx tsc --noEmit` и `npm run lint` — чисто.
2. `npm run tauri dev`.
3. YouTube, `privacyStatus: public`, время +10 минут → видео грузится сразу, статус `scheduled`,
   в YouTube Studio видно «Запланировано» на это время; приложение можно закрыть.
4. YouTube, `privacyStatus: unlisted` + дата → внятная ошибка валидации до старта.
5. Instagram, время +3 минуты → в логах виден `stage` сразу (контейнер создан), приложение открыто,
   в T проходит `media_publish`, пост появляется в профиле в указанную минуту.
6. Instagram, время +2 дня → сразу задач загрузки нет, в очереди `stage` на `T - 12ч`
   (проверить `scheduler.listJobs()` в логах), статус `scheduled` без `uploadedVideoId`.
7. TikTok, время +3 минуты → загрузка стартует ровно в T (не раньше), UI это и обещает.
8. Отмена запланированной задачи из `UploadProgress` → задача уходит из очереди, статус `cancelled`,
   повторно не срабатывает.
9. Перезапуск приложения с запланированной задачей на X/IG/TikTok → задача не восстанавливается и
   ничего не публикуется (ожидаемое поведение по принятому решению).
10. Логи: `openLogsFolder()` из топбара — записи от `scheduler`, без токенов.
