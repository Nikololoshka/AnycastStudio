---
paths:
  - "backend/**/*.py"
---

# Backend

Flow: `views / tasks → services use cases → platforms/<p> → platform API`.

- `platforms/` imports nothing from Django, the apps or `services`;
  `services/core/` and `services/usecases/` import nothing from Django, Celery
  or the apps. `test_architecture.py` enforces both.
- Every platform folder has the same shape as `platforms/youtube/`; no imports
  between platform folders.
- New platform: its folder plus entries in `platforms/platform_catalog.py`,
  `platforms/platform_configs.py` and `services/wiring.py::Container.platform_configs`.
- No public module-level functions in `platforms/`, `services/core/`,
  `services/usecases/`. Internal values are frozen dataclasses; pydantic only
  parses external input (platform responses, request bodies).
- Use cases are `async` and reach DB, queue and cache only through ports.
  Views and tasks are sync and enter via `container().run(...)`.
- A view calls a use case only if it answers in milliseconds; uploads and
  confirmations go to Celery tasks.
- Every DB method in a repository is sync and wrapped in `sync_to_async`, so a
  transaction never spans more than one call.
- A publish interactor works with `PublishJob`, never a model. A step that must
  not run twice answers `ReadyToCommit`; `CommitGuard` marks it before `commit`.
- Every platform HTTP call goes through its `PlatformHttp`. Retry transient
  failures only via `RetryPolicy` and only where a retry is safe.
- Platform failure → `PlatformError` with `PlatformFailure`. API refusal →
  domain error from `services/core/domain/` (`NotFound`, `Conflict`, …).

## API

- No DRF. Every response carries a `status` string; the HTTP code comes from
  `common/responses/contract.py::HTTP_STATUS`. New outcome → new entry there,
  not a new body shape.
- One file per endpoint group, `<app>/views/<name>.py`; follow
  `publishing/views/publications.py` for decorators and view shape.
