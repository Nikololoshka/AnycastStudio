# Выделить `services/` из `platforms/`

## Context

Сейчас в `backend/platforms/` лежат две разные вещи:
1. **платформы**: `Platform`, интерфейсы `auth/`, `publish/` и `http/`, `PlatformFailure`, а также `youtube/`, `tiktok/`, `instagram/`, `x/` и `PlatformCatalog`;
2. **сервисы над платформами**: use cases (`core/usecases/`), их порты (`core/ports/`), значения (`core/accounts/`, `core/publications/`), доменные ошибки (`core/domain/`) и `tiktok/creator/creator_info_service.py`.

Обвязка второй части тоже разбросана: `config/wiring.py`, `publishing/tasks.py`, `social/tasks.py`, `media/tasks.py` и `publishing/queue.py`.

Цель: вынести вторую часть в отдельный пакет верхнего уровня `backend/services/` и собрать в нём весь нужный ей core, wiring, очередь и все Celery-задачи. Зависимости идут в одну сторону: `services → platforms`. `platforms` о `services` не знает и остаётся Django-free.

Поведение не меняется: файлы переезжают, меняются только импорты. Имена Celery-задач остаются прежними, поэтому beat-расписание и сообщения, которые уже стоят в Redis, продолжают работать.

⚠ Переезжают `TokenService`, `AccountService` и `ConnectFlow`. Это зона OAuth и токенов из CLAUDE.md. Код в них не меняется, только пути. Одобрение этого плана считаю одобрением переноса.

## Целевая структура

```
backend/services/
├─ __init__.py
├─ core/                      ← без Django
│  ├─ accounts/               ← platforms/core/accounts/
│  ├─ publications/           ← platforms/core/publications/
│  ├─ domain/                 ← platforms/core/domain/
│  └─ ports/                  ← platforms/core/ports/
├─ usecases/                  ← без Django
│  ├─ accounts/               ← platforms/core/usecases/accounts/
│  ├─ publications/           ← platforms/core/usecases/publications/
│  └─ tiktok/creator_info_service.py  ← platforms/tiktok/creator/creator_info_service.py
├─ wiring.py                  ← config/wiring.py (Services, Container, container())
├─ queue.py                   ← publishing/queue.py (CeleryTaskQueue)
├─ tasks.py                   ← publishing/tasks.py + social/tasks.py + обёртки media/tasks.py
└─ tests/
   ├─ fakes/{accounts,clock,publishing}.py  ← platforms/tests/fakes/
   ├─ test_account_scenarios.py, test_publication_scenarios.py ← platforms/tests/core/
   ├─ test_wiring.py          ← config/tests/test_wiring.py
   └─ test_architecture.py    (новый)
```

В `platforms/` остаётся: `core/` с `auth`, `publish`, `http`, `platform*.py`, `scheduling.py` и `validation_result.py`, папки платформ, `platform_catalog.py` и `platform_configs.py`. В `platforms/tiktok/creator/` остаются `TikTokCreatorInfo` и `answers/`: это вызов API платформы.

## Шаги

Всё переносится через `git mv`, чтобы сохранить историю.

1. **Перенос core.** Пакеты `platforms/core/{accounts,publications,domain,ports}` переезжают в `services/core/`. Относительные импорты ядра платформ (`..auth`, `..publish`, `..platform_type`) заменяю на `from platforms.core import …`.

2. **Перенос use cases.** `platforms/core/usecases/*` переезжает в `services/usecases/`. Импорты `from ...platform_error` и подобные заменяю на `platforms.core`, а `from ...ports` и подобные — на `from ...core.ports`. Чтобы не ходить во внутренний модуль, добавляю `PlatformRegistry` в экспорт `platforms/core/__init__.py`.
   `CreatorInfoService` переезжает в `services/usecases/tiktok/` и импортирует `TikTokCreatorInfo` из `platforms.tiktok.creator`. Его экспорт убираю из `platforms/tiktok/creator/__init__.py`.

3. **Wiring.** `config/wiring.py` переезжает в `services/wiring.py`. Меняются импорты, `dispatch_uid` получает значение `"services.wiring.forget_container"`, а `CeleryTaskQueue` берётся из `services.queue`. Ленивые импорты репозиториев приложений остаются как есть.

4. **Очередь и задачи.**
   - `publishing/queue.py` переезжает в `services/queue.py` и импортирует `from . import tasks`.
   - `services/tasks.py` собирает все `shared_task` с прежними `name=` (`publishing.*`, `social.refresh_expiring_tokens`, `media.sweep_*`). `publishing/tasks.py`, `social/tasks.py` и `media/tasks.py` удаляю.
   - Тела sweep-задач (`sweep_upload_sessions` и `sweep_unused_assets`) переезжают в `media/services.py` к `abort`, `unused_assets` и `delete_asset`. `media/management/commands/sweep_media.py` и `media/tests/test_sweeps.py` импортируют их оттуда.
   - В `config/celery.py` меняю `app.autodiscover_tasks()` на `app.autodiscover_tasks(["services"])`. `services` не становится Django-приложением.

5. **Импорты в приложениях.** Внутри файлов меняются только пути:
   - `platforms.core.{accounts,publications,domain,ports}` → `services.core.…`. Затронуты `social/models.py`, `social/repositories.py`, `publishing/models.py`, `publishing/repositories.py`, `publishing/views/publications.py`, `common/responses/domain.py` и `common/caching/__init__.py`.
   - `config.wiring` → `services.wiring`. Затронуты `social/views/*`, `publishing/views/*` и тестовые base-классы.
   - `platforms.core.usecases.…` → `services.usecases.…` в тестах `publishing/` и `social/`.
   - `"publishing.tasks.…"` в `mock.patch` и `from publishing import tasks` → `services.tasks`.
   - Миграции не нужны: `TargetStatus`, `AccountStatus` и `OAuthSessionStatus` остаются теми же `TextChoices`/`StrEnum`, меняется только путь импорта.

6. **Тесты.**
   - Фейки портов (`accounts.py`, `clock.py`, `publishing.py`) переезжают в `services/tests/fakes/`. `http.py` и `platform.py` остаются в `platforms/tests/fakes/`, тесты `services` импортируют их оттуда.
   - Сценарные тесты use cases переезжают в `services/tests/`. Если `platforms/tests/base.py` нужен этим тестам, импортирую его оттуда же.
   - В `platforms/tests/core/test_architecture.py` в `FORBIDDEN_ROOTS` добавляется `"services"`.
   - Новый `services/tests/test_architecture.py` в том же стиле, с классом `SourceModule`, проверяет три вещи:
     - `services.core` и `services.usecases` не импортируют `django`, `celery`, `config` и приложения;
     - в `services.core` и `services.usecases` нет публичных функций уровня модуля;
     - `services.core` не импортирует `services.usecases`.
   - `config/tests/test_wiring.py` переезжает в `services/tests/`.

7. **Документация.**
   - CLAUDE.md: Architecture, Architectural Rules, Repository Structure, File Placement, Testing (путь `services.wiring.Container.open_session`), Sensitive Areas и Human Approval (`services/usecases/accounts/` вместо `platforms/core/usecases/accounts/`), таблица библиотек.
   - Пути в `docs/architecture.md`, `docs/platforms/adding-a-platform.md` и `docs/publishing-flow.md`.
   - ADR 0002 и 0003 не трогаю: это записи решений на момент принятия. Добавляю короткий `docs/adr/0004-services-package.md` о разделении и направлении зависимостей.

Незакоммиченная правка в `platforms/platform_catalog.py` (аннотация типа) сохраняется. Коммит делаю только по просьбе.

## Проверка

- `cd backend && .venv/Scripts/python manage.py test --settings=config.settings.test`: все тесты зелёные, включая оба архитектурных.
- Остатков старых путей нет. Grep по `platforms\.core\.(accounts|publications|ports|domain|usecases)`, `config\.wiring`, `publishing\.tasks`, `social\.tasks`, `media\.tasks` и `publishing\.queue` в `backend/`, `docs/` и `CLAUDE.md` ничего не находит, кроме ADR 0002/0003.
- Регистрация задач:
  `.venv/Scripts/python -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev');django.setup();from config.celery import app;app.loader.import_default_modules();print(sorted(n for n in app.tasks if not n.startswith('celery.')))"`.
  Должны быть все семь имён из `CELERY_BEAT_SCHEDULE`, а также `publishing.run_target` и `publishing.confirm_target`.
- `.venv/Scripts/python manage.py check` и `manage.py sweep_media` отрабатывают.
