# Рефакторинг: `platforms` как ядро бизнес-логики

Дата: 2026-09-28. Коммиты `22804ef` … `fb6d718` в `master`. Решения записаны в
`docs/adr/0002-platforms-core.md`.

## Зачем

Логика публикации и подключения аккаунтов была разнесена по трём местам:
`publishing/` (pipeline, schedule, services, publishers), `social/` (refresh
токенов, OAuth-сессии, логика во views) и `platforms/` (свободные функции,
читавшие настройки Django). Одно правило приходилось менять в нескольких
файлах; цепочка «токен → вызов → refresh при 401 → повтор» была написана
трижды.

## Что стало

- **`backend/platforms/` — единственное место бизнес-логики**, без единого
  импорта Django. Это проверяет `platforms/tests/core/test_architecture.py`.
- **`platforms/core/`**:
  - утилиты: `http/` (`PlatformClient`, `RetryPolicy`, `FailureClassifier`),
    `upload/` (`UploadDriver`, `UploadSession`, `TokenRejectionGuard`),
    `capabilities/`, `errors.py`, `config.py`;
  - интерфейсы: `ports/` (репозитории, `TaskQueue`, `UnitOfWork`, `Clock`,
    `Cache`, `AccessTokens`) и `platform.py` (`Platform`, `PlatformCatalog`,
    `PlatformFactory`);
  - сценарии: `publishing/` (`PublicationService`, `PublicationPipeline`,
    `ConfirmationPoller`, `DeferredDispatcher`, `CommitGuard`) и `auth/`
    (`TokenService`, `AccountService`, `ConnectFlow`).
- **Одинаковая структура у каждой платформы**: `client.py`, `auth/`,
  `upload/`, `publish/`, `options/`, `platform.py`. Платформы не импортируют
  друг друга; собираются фабриками в `platforms/registry.py`.
- **Django-приложения — адаптеры**: модели, тонкие views и Celery-задачи,
  репозитории (`publishing/repositories.py`, `social/repositories.py`),
  `publishing/queue.py`, `common/transactions`, `common/caching`. Всё
  собирается в `config/wiring.py::container()`, который сбрасывается при
  `override_settings`.
- **Ошибки**: единая иерархия `PlatformError` + `FailureType`; отказы API —
  доменные исключения (`NotFound`, `Conflict`, …), которые
  `common/responses::domain_errors` превращает в контракт статусов.
- **ООП и значения**: публичных функций в `platforms` нет; внутренние
  значения — frozen dataclass (`PublishJob`, `PublicationDraft`, `ResumeState`
  через `replace()`), pydantic — только для внешних данных.
- **Двухфазный commit**: неидемпотентный шаг (сейчас пост в X) объявляется
  `ReadyToCommit`; ядро ставит метку `commit_started` до вызова и не повторяет
  шаг, если ответ не пришёл.

## Изменения поведения

Поведение и HTTP API не менялись, кроме деталей хранения:

- метка X `posting_started` → `commit_started` (миграция
  `publishing/0003_commit_marker` переименовала её в существующих строках);
- время начала подтверждения хранится как ISO-строка; старые float-метки
  читаются;
- `error` таргета всегда содержит ключ `details` (раньше не для всех типов).

## Тесты

426 → 481. Добавлены unit-тесты сценариев на фейках портов
(`platforms/tests/fakes/`, без БД), архитектурный тест и тест миграции.
Тесты платформ разложены по `platforms/tests/<platform>/`, тесты ядра — в
`platforms/tests/core/`. Мок сети: `platforms.core.http.transport.requests.request`.

## Что не сделано

- Ручная проверка с Redis, воркером, beat и реальными платформами.
- Слабые места из `docs/publishing-flow.md` §9 не исправлялись; теперь каждое
  правится в одном классе (`DeferredDispatcher`, `PublicationService.create`,
  `ConfirmationPoller`, `XPublisher.resolve_uncertain`).
- Коммит `323eb93` (шаг 2) в истории не проходит `manage.py check` из-за
  циклического импорта; исправлено следующим коммитом.
