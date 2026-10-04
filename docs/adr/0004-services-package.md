# 4. The use cases live in `services`, apart from the platforms

Date: 2026-10-04
Status: accepted; amends 0002 and 0003

## Context

After ADR 0003, `backend/platforms/` held two different things:

- the platforms themselves: the `Platform` interface with its `auth/`,
  `publish/` and `http/` pieces, `PlatformFailure`, one folder per platform
  and the catalog;
- the business logic built on them: the use cases, their ports, the values
  they share (`accounts/`, `publications/`), the domain errors, and TikTok's
  `CreatorInfoService`, which caches through a port.

The wiring of the second part was spread over the apps: the container sat in
`config/wiring.py`, the Celery tasks in `publishing/`, `social/` and `media/`,
and the queue adapter in `publishing/queue.py`.

## Decision

The business logic moves to a top-level package, `backend/services/`:

- `services/core/` holds the shared values (`accounts/`, `publications/`),
  the domain errors (`domain/`) and the async ports (`ports/`);
- `services/usecases/` holds the use cases (`accounts/`, `publications/` and
  `tiktok/`);
- `services/wiring.py` is the container, `services/queue.py` the
  `CeleryTaskQueue`, and `services/tasks.py` every Celery task, the media
  sweeps included.

The dependency runs one way, `services → platforms`. `platforms` knows nothing
of `services` and stays free of Django. In `services`, `core/` and
`usecases/` import nothing from Django, Celery or the apps. Only the entry
points (`wiring.py`, `queue.py` and `tasks.py`) reach the adapters. An
architecture test in each package enforces this.

The task names do not change (`publishing.*`, `social.*` and `media.*`), so
the beat schedule and the messages already queued keep working. Celery
discovers the tasks through `app.autodiscover_tasks(["services"])`; `services`
is not a Django app.

## Consequences

- A new platform touches `platforms/<p>/`, the catalog and configs, and
  `services/wiring.py::Container.platform_configs`.
- A new rule about publishing or accounts is a use case in
  `services/usecases/`; a new background job is a task in `services/tasks.py`.
- The tests of the use cases live in `services/tests/` with the fakes of the
  ports. The fakes of the network and of a platform stay in
  `platforms/tests/fakes/`.
- The sweep logic of `media` lives in `media/services.py`, next to what it
  sweeps. `services/tasks.py` only schedules it.
