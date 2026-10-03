# 3. Platforms on asyncio, uploads without resume, one failure vocabulary

Date: 2026-10-03
Status: accepted; amends 0002

## Context

ADR 0002 put the publishing and account rules in `backend/platforms/` behind
ports. Each platform was a composition of a provider, an uploader with a
resumable state machine, a publisher and a validator, all synchronous on
`requests`, and every failure was a `FailureType`.

Two things did not hold up:

- The resumable upload states were most of each platform's code and most of
  its tests, yet resuming only helps when a worker dies mid-upload. For a
  couple of people publishing their own videos that is rare, and the
  platforms disagree on how a resumed session behaves (TikTok cannot say what
  it received, X and Instagram expire sessions).
- `FailureType` described HTTP more than outcomes. "authentication" meant both
  "refresh and try again" and "reconnect the account", so the use cases had to
  look at exception classes to tell them apart.

The platforms were rewritten in a parallel package and then swapped in.

## Decision

### A platform is two interactors

`Platform` exposes an `AuthorizationInteractor` (`create_auth_request`,
`create_auth_token`, `refresh_auth_token`, `fetch_auth_profile`,
`revoke_auth_token`) and a `PublishInteractor` (`upload`, `publish`,
`confirm`, `commit`, `resolve_uncertain`), plus its capabilities and validator.
The calls are `async`. HTTP goes through `aiohttp` with one `PlatformHttp`
subclass per platform; YouTube's resumable upload goes through
`google-api-python-client` in a thread.

`upload` is an async generator of `UploadProgress`; the last event carries the
media id. Leaving the loop closes the generator, and with it the file.

### Values, ports, use cases

`platforms/core/` keeps values (`accounts/`, `publications/`, `domain/`), async
ports (`ports/`) and the use cases (`usecases/accounts/`,
`usecases/publications/`) apart, so nothing a port names imports a use case.
The Django adapters wrap each database method in `sync_to_async`, so a
transaction stays inside one synchronous call and never spans a network call.

### Sync callers enter through `async_to_sync`

Views and Celery tasks stay synchronous and call `container().run(...)`, which
opens an aiohttp session and a `PlatformCatalog` for the call and runs the use
case through `async_to_sync`. We chose that over `asyncio.run` because it
brings the ORM calls back to the calling thread: the test transaction and the
worker's connection are the ones the use case writes through.

### An upload always starts from scratch

Nothing about an upload session is stored. A target that a stopped worker
abandoned in `validating`, `uploading` or `publishing` is failed by
`StaleTargetSweeper` (a beat task), and a retry clears the media id and the
confirmation state. What still survives a task is the confirmation:
`PublicationTarget.confirmation_state` keeps the platform's state, the polls,
the window and the `commit_started` mark, because confirming spans minutes by
nature.

### One failure vocabulary

Every failure is a `PlatformError` with a `PlatformFailure`: `network` and
`rate_limited` are transient; `token_rejected` asks for one refresh;
`grant_revoked` and `scope_missing` mark the account for reconnecting;
`misconfigured` blames our client and leaves the account alone; `invalid`,
`file_rejected`, `media_missing` and `refused` are verdicts; `unconfirmed`
means a post may exist. The stored `error` of a target is
`{"failure", "message", "details"}`, and the browser picks its text by
`failure`.

## Consequences

- A platform folder is `core/`, `auth/`, `publish/`, `<p>_capabilities.py`,
  `<p>_validator.py` and `<p>_platform.py`, registered in `platform_catalog.py`
  and `platform_configs.py`; its config is built from the settings in
  `config/wiring.py`.
- A killed worker costs a re-upload after the person retries; it no longer
  continues by itself.
- Backend tests fake the network with `platforms/tests/fakes/http.py`
  (`FakeSession`) and YouTube with an `httplib2`-style double, so the real
  chunking and retry still run.
- Migration `publishing/0004` renamed `resume_state` to `confirmation_state`,
  dropped upload resume points and rewrote stored failures to the new
  vocabulary.
