# 2. `platforms` holds the business logic; Django apps adapt it

Date: 2026-09-28
Status: accepted; amended by 0003 (platforms on asyncio, uploads without resume, PlatformFailure)

## Context

After the four platforms were ported, the rules for publishing and for
connecting accounts lived in three places:

- `publishing/` — the pipeline (claim, validate, upload, publish, confirm),
  the deferred schedule, the create/cancel/retry services and one publisher
  per platform that turned a `PublicationTarget` row into platform calls;
- `social/` — token refresh with a lease, saving and disconnecting accounts,
  the OAuth `state` sessions, and logic inside the callback and creator-info
  views;
- `platforms/` — HTTP, the OAuth providers and the upload protocols, mostly as
  module-level functions reading Django settings.

A change to one rule, such as how a post that got no answer is protected
from being sent twice, touched the pipeline, one publisher and the model
row at once. The same "get a token, call, refresh once on 401, call again"
sequence was written three times.

## Decision

### One package for the rules

`backend/platforms/` holds all of it:

- `core/` — the shared toolkit (`http/`, `upload/`, `capabilities/`,
  `errors.py`, `config.py`), the interfaces (`ports/`, `platform.py`) and
  the use cases (`publishing/`, `auth/`);
- one folder per platform with the same layout: `client.py`, `auth/`,
  `upload/`, `publish/`, `options/`, `platform.py`;
- `registry.py`, which builds the catalog from one factory per platform.

### Ports and adapters

`platforms` imports nothing from Django or from the apps. The use cases
depend on abstract repositories and services in `core/ports/`
(`TargetRepository`, `PublicationRepository`, `AccountRepository`,
`OAuthSessionRepository`, `TaskQueue`, `UnitOfWork`, `Clock`, `Cache`,
`AccessTokens`). The apps implement them on the ORM, Celery and the Django
cache, and `config/wiring.py` assembles everything once in a lazy container
that forgets itself when a setting changes.

We chose this over letting `platforms` import the models because it keeps
the rules testable without a database (the fakes in `platforms/tests/fakes/`
implement the same interfaces) and because an import rule is easy to
enforce: `platforms/tests/core/test_architecture.py` fails on any Django
import. The price is one adapter per port and one mapping from rows to
value objects.

### Shapes that follow from it

- A platform is a composition (`Platform`: provider, publisher, validator,
  capabilities) built by a `PlatformFactory`, not one class that does
  everything.
- The publisher works on a `PublishJob` value, never on a model. A step that
  cannot be repeated safely is announced with `ReadyToCommit`; the pipeline
  marks it, calls `commit`, and refuses to send it again when no answer came
  back. The platform does not write to the database itself.
- Every platform failure is a `PlatformError` with a `FailureType`; the API
  refusals are domain exceptions that `common/responses::domain_errors`
  maps onto the status contract.
- Behaviour lives in classes and value objects. Modules expose no public
  functions; the architecture test checks that too.

## Consequences

- A new platform is a folder and one line in `registry.py`; nothing in
  `publishing/` or `social/` changes.
- A rule such as "validate before accepting a publication" is written once
  in the use case and reaches the worker and the API alike.
- The network mock for backend tests is
  `platforms.core.http.transport.requests.request`.
- Upload resume states are frozen and advance with `dataclasses.replace`.
- The X "posting_started" mark became the generic `commit_started`; a data
  migration renamed it on rows already stored.
