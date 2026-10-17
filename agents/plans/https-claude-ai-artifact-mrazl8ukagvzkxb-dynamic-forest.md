# Вариант C: настройки платформ в публикации + умолчания в «Платформах»

## Context
Макет (canvas «Видео-публикатор», артборды `UploadC`, `UploadCOpen`, `Platforms`) задаёт вариант C:
карточки платформ над формой публикации, по «Настроить» — боковая панель (Drawer) с превью и
настройками этой публикации; раздел «Платформы» хранит умолчания для новых публикаций.
Сейчас: настройки платформ раскрываются Disclosure прямо в `ComposerPlatformsCard`, а «умолчания» —
это последние использованные настройки (persistMiddleware пишет их в localStorage при каждом изменении).

Решения пользователя:
- Название/описание/хэштеги — только общие, своего текста по платформам нет.
- Умолчания в localStorage, без шаблонов текста.
- Остальные экраны не трогать. Рабочее дерево содержит чужие незакоммиченные правки — работать поверх, не откатывать.

## Что сделать

### 1. Умолчания платформ (localStorage)
- `services/storage/localSettings.ts`: ключ `defaultPlatforms` (список «выбирать по умолчанию»); `platformSettings` остаётся — теперь это умолчания настроек.
- `api/`: `platformDefaultsApi.ts` по образцу `profileApi.ts` (queryFn на localStorage): `getPlatformDefaults` → `{ selected, settings }`, `updatePlatformDefaults(patch)`. Экспорт из `api/index.ts`.
- `app/store/persistMiddleware.ts`: убрать слушатель `setPlatformSettings` — композер больше не перезаписывает умолчания.
- `composerSlice.initialComposer`: `selectedPlatforms` из `defaultPlatforms` (нет — все), `platformSettings` как сейчас из `platformSettings`. Новый reducer `resetPlatformSettings(platform)` → умолчание из хранилища (normalize).

### 2. Раздел «Платформы» (`features/accounts/PlatformsScreen.tsx`, `PlatformDetail`)
Для подключённого аккаунта вместо `detail.settingsNote` блок умолчаний:
- Switch «Выбирать по умолчанию» + подсказка.
- «Видимость по умолчанию» — только YouTube (`privacyStatus`, `SettingSelect`, опции `YOUTUBE_PRIVACY_OPTIONS`).
- TikTok: подсказка, что видимость выбирается в каждой публикации (правило TikTok, `privacyLevel` всегда сбрасывается в null).
- Instagram/X: видимости нет — только переключатель.
- Инфо-плашка: «Формат, обложка и всё, что есть только у {platform}, настраивается в каждой публикации — кнопкой «Настроить»». Сохраняется сразу (без кнопок Сохранить/Отменить — localStorage, как в Account).

### 3. Композер: карточки платформ (`ComposerPlatformsCard.tsx`)
- Секция «Куда публикуем» во всю ширину между заголовком и колонками (`ComposerScreen.tsx`: вынести из правой колонки; файл/текст/время не трогаем). Справа от заголовка — «выбрано N · по умолчанию из раздела Платформы» (ссылка).
- Сетка `grid-cols-[repeat(auto-fill,minmax(220px,1fr))]`, карточка: `PlatformGlyph`, имя, аккаунт, `Switch`; ряд чипов-сводки; кнопка «Настроить» (lucide `SlidersHorizontal`) если выбрана; «Войти снова» (истёк) / «Подключить» (нет аккаунта) — ссылки на `/platforms`. Выделение рамкой карточки, чья панель открыта.
- Чипы: «не публикуем» если не выбрана; иначе видимость (YouTube), «нужно выбрать видимость» (TikTok при null, warning), «изменено» (warning) если настройки ≠ умолчаниям.
- Disclosure убрать.

### 4. Композер: панель платформы (новый `features/composer/PlatformSettingsDrawer.tsx`)
HeroUI 3 `Drawer` справа (~580px, full на телефоне), Esc/клик по фону закрывают; изменения уже в slice → автосейв черновика как сейчас.
- Шапка: глиф, имя, «{аккаунт} · настройки этой публикации», закрыть; Tabs-переключатель по выбранным платформам, точка = изменено.
- Тело (скролл): превью — вертикальное 9:16 для TikTok/Instagram (кадр `video.thumbnailDataUrl`, аккаунт, описание+хэштеги), горизонтальное 16:9 для YouTube/X (кадр, название, аккаунт); подпись «Так пост будет выглядеть в …» + заметка по платформе (обрезка до 9:16 и т. п.). Текст только для показа — берётся из общего.
- Затем существующий `PLATFORM_PANELS[platform]` (секция «Только в {PLATFORM}») — панели не переписываем.
- Ссылка «Не публиковать в {platform}» → `togglePlatform` + закрыть.
- Низ: «Сбросить всё» (`resetPlatformSettings`), «Следующая», «Готово».
- Состояние «какая открыта» — локальный `useState` в `ComposerPlatformsCard`.

### 5. i18n
Новые ключи в `locales/{en,ru}/composer.json` (карточки, панель, превью, чипы) и `accounts.json` (умолчания); удалить `detail.settingsNote`/`detail.compose`, `platforms.settings` если больше не используются. en и ru синхронно.

## Что из макета не получится (сообщить пользователю)
- Свой текст по платформам — убран по решению пользователя.
- Своё время выхода для платформы — сервер публикует все цели в одно `publish_at`.
- «Формат» (Shorts / обрезать 9:16 / с полями), своя обложка-картинка, плейлист, теги поиска, язык, отметки людей, место, скрыть лайки, поделиться в Facebook, модерация комментариев YouTube — нет в API-интеграции/настройках сервера. Обложка-кадр TikTok/Instagram уже есть в их панелях.
- VK Видео и Facebook — платформ нет в приложении.
- Шаблоны текста — не делаем (решение пользователя).
- Видимость по умолчанию — только YouTube (TikTok требует явный выбор, у Instagram/X её нет).
- Блок «Перед публикацией» и обложка в общей форме — вне scope (не трогаем остальное).

## Файлы
- `frontend/src/features/composer/{ComposerPlatformsCard.tsx, ComposerScreen.tsx, composerSlice.ts, PlatformSettingsDrawer.tsx (новый)}`
- `frontend/src/features/accounts/PlatformsScreen.tsx`
- `frontend/src/api/{platformDefaultsApi.ts (новый), index.ts}`, `frontend/src/app/store/persistMiddleware.ts`, `frontend/src/services/storage/localSettings.ts`
- `frontend/src/locales/{en,ru}/{composer,accounts}.json`
- Бэкенд не меняется; `platforms/*/settings.ts` умолчания не трогаем (контракт-тест).

## Проверка
- `cd frontend && npx tsc --noEmit && npm run lint && npm test`
- Бэкенд не затронут; при желании `backend: .venv/Scripts/python manage.py test --settings=config.settings.test`.
- Вручную (skill `run`): «Платформы» → выключить «выбирать по умолчанию» у X, YouTube видимость = public → новая публикация: X не выбран, у YouTube чип «Публично»; «Настроить» → Drawer, переключение вкладок, точка после изменения, «Сбросить всё», «Не публиковать», Esc.
