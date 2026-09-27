# Unify platform implementations

## Context

The four platforms (YouTube, TikTok, Instagram, X) were ported one by one, and each copied the
previous one. The result is the same machinery written four times with small drifts:

- `Cancelled` / `NeedsFreshToken` — identical in `instagram/errors.py`, `tiktok/errors.py`,
  `x/errors.py`, and again inside `youtube/upload.py`. Each publisher then translates them into
  `publishing/publishers/outcome.py` exceptions with the same `except` blocks.
- "AUTHENTICATION failure → NeedsFreshToken" — `fresh_token_on_rejection` in `instagram/status.py`
  and `x/api.py`, inline `try/except` in `tiktok/upload.py`, `tiktok/status.py`, `youtube/upload.py`.
- `api.py::_attempt` + `send` — the same two functions in instagram, tiktok, x; only `failure_of`
  differs. YouTube has no `api.py` and builds `Bearer` headers by hand in `upload.py` and `publish.py`.
- `LABEL` lives in `api.py` (instagram, x) or `capabilities.py` (youtube, tiktok).
- `upload.py` — every platform has the same loop (cancel check → read piece → length check → send →
  advance → `on_progress`) and the same hand-written `ResumeState.as_dict` / `ResumeState.of`.
- `publishing/publishers/<p>.py` — plain modules with an implicit contract (`capabilities`,
  `validate`, `upload`, `publish`, `confirm`), typed as `ModuleType`. `_caption`, the upload wrapper
  and "PROCESSING with `confirming_since` / `polls`" are repeated. YouTube has no `confirm`.
- `publishing/views/platforms.py::CAPABILITIES` repeats the `PUBLISHERS` registry.
- OAuth providers (~130 lines each): `_send`, `_client_id` / `_client_secret`, `_post_token`,
  `authorize_url` differ only in parameters.
- Public names drift: `container_status` / `publish_status` / `processing_status`;
  `watch_url` / `post_url` / `permalink`.

Goal: one shape every platform fits, so a fifth platform fills in parameters and platform-specific
steps only. Behaviour does not change; the existing tests (mocked at
`platforms.http.transport.requests.request`) are the safety net and must stay green after each stage.
Each stage is a separate commit.

## Target shape

```
platforms/
├─ http/        + send(method, url, *, label, failure_of=classify, attempts=None, **kwargs)
├─ upload/      NEW: UploadCancelled, NeedsFreshToken, fresh_token_on_rejection,
│               ResumableState, read_piece, UploadSession (Protocol), drive()
├─ oauth/       + OAuth2Provider base (stage 6)
└─ <p>/
   ├─ api.py            LABEL, roots, auth header, failure_of, call()     (youtube gets one)
   ├─ capabilities.py   capabilities(), validate()
   ├─ upload.py         ResumeState(ResumableState), <P>Session(UploadSession), upload()
   ├─ status.py         fetch_status(), failure_of(), post_url()
   ├─ video_options.py
   └─ oauth.py          <P>Provider(OAuth2Provider)

publishing/publishers/
├─ publisher.py   NEW: Publisher base class
├─ outcome.py     Published + awaiting_confirmation()   (Interrupted classes removed)
└─ <p>.py         class <P>Publisher(Publisher)
```

## Stages

### 1. Shared interruptions — `platforms/upload/`

- `platforms/upload/errors.py`: `UploadCancelled(state: dict)` and `NeedsFreshToken(state: dict | None, message)`.
  The platform stores `state.as_dict()`, so the exception already carries what `resume_state` stores.
- `platforms/upload/tokens.py`: `fresh_token_on_rejection(action, state=None)` — the one copy.
- Delete `instagram/errors.py`, `tiktok/errors.py`, `x/errors.py`, and the two classes in
  `youtube/upload.py`. Replace every inline AUTHENTICATION → NeedsFreshToken block with the helper.
- `publishing/pipeline.py` catches `platforms.upload.UploadCancelled` / `NeedsFreshToken` directly;
  on `stale.state is None`, it keeps `target.resume_state` (today's `resume or {}` in each publisher).
- Remove `Interrupted`, `UploadCancelled`, `NeedsFreshToken` from `publishing/publishers/outcome.py`
  and the translating `except` blocks from all four publishers.
- `social/views/creator_info.py` switches from `tiktok.NeedsFreshToken` to the shared class.

### 2. One request path — `platforms/http/send`

- Add `send(method, url, *, label, failure_of=classify, attempts=None, **kwargs)` to `platforms/http/`
  (wraps `request` + `failure_of` + `with_retry`) — replaces `_attempt` + `send` in instagram, tiktok, x.
  TikTok's `failure.details = error_code(...)` moves into a `tiktok/api.py::failure_of`.
- New `youtube/api.py`: `LABEL`, `bearer()`, `send()`; `youtube/upload.py`, `youtube/publish.py`
  and `youtube/oauth.py` use it. `LABEL` moves to `api.py` in every platform.

### 3. Resume state and the upload loop — `platforms/upload/`

- `ResumableState` (dataclass base): `as_dict()` via `dataclasses.asdict`; `of(raw)` returns `None`
  when `raw` is not a dict or a field without a default is missing/empty, and casts each value by the
  field type. The four `ResumeState` classes keep only their fields and platform properties
  (`expired`, `uploaded_bytes`, `bounds_of`, …).
- `read_piece(handle, offset, length) -> bytes` raises `PlatformFailure(FILE, "The video is shorter…")`.
- `UploadSession` Protocol: `state`, `done`, `uploaded`, `send_next(handle)`, `finish() -> str`.
- `drive(session, *, path, size, on_progress, should_cancel) -> str`: open file, loop while not
  `done` — cancel check (`UploadCancelled(session.state.as_dict())`), `send_next`, `on_progress`;
  then `finish()`.
- Each `upload.py` keeps `start` / `_resumed` (platform-specific: YouTube asks the server for the
  offset, Instagram reads `bytes_transferred`, TikTok/X check expiry) and a small session class:
  - YouTube: `send_next` PUTs a piece, completion comes from the response, `finish` returns the id
    already received; keeps the "no progress for N chunks" guard.
  - TikTok: fixed chunk plan, last chunk must answer 201; `finish` returns `publish_id`.
  - X: segments; `finish` calls `finalize`.
  - Instagram: offset-based; `finish` returns `container_id`.
- `upload(...)` in every platform = choose/start state, `return drive(Session(...), ...)`.
  `on_progress(uploaded, total, state_dict)` — the lambda in each publisher disappears.

### 4. Uniform public surface per platform

Every `platforms/<p>/__init__.py` exports the same core names: `LABEL`, `<P>Provider`,
`capabilities`, `validate`, `upload`, `ResumeState`, `VideoOptions`, `video_options_of`, plus
`fetch_status`, `failure_of`, `post_url` where the platform confirms. Renames:
`container_status` / `publish_status` / `processing_status` → `fetch_status`; YouTube `watch_url`,
Instagram `permalink` → `post_url`. Platform-only extras (`publish_container`, `create_post`,
`creator_info`, `schedule`) stay under their own names.

### 5. Publisher classes — `publishing/publishers/`

- `publisher.py::Publisher` base class:
  - `platform` (module from `platforms/`), `capabilities()` delegating to it;
  - `caption(target)` default via `platform.caption_of(title, description, hashtags)`;
  - abstract `validate(target)`, `upload(target, token, resume, on_progress, should_cancel)`;
  - `publish(target, media_id, token)` default `awaiting_confirmation()`;
  - `confirm(target, token)` default raises `NotImplementedError` (YouTube never reaches PROCESSING).
- `outcome.py::awaiting_confirmation(**extra) -> Published` replaces the three copies of
  `Published(Status.PROCESSING, resume_state={"confirming_since": …, "polls": 0})`.
- `YouTubePublisher`, `TikTokPublisher`, `InstagramPublisher`, `XPublisher` keep only what differs
  (metadata/post info building, TikTok creator checks, Instagram publish step, X post-once logic).
- `PUBLISHERS: dict[str, Publisher]`; `publisher_for` unchanged for callers.
- `publishing/views/platforms.py` builds from `PUBLISHERS` and drops `CAPABILITIES`.
- CLAUDE.md "File Placement Rules": a new platform needs a line in `social/providers.py` and
  `publishing/publishers/__init__.py` only.

### 6. OAuth base — **ask for approval before starting** (sensitive area)

- `platforms/oauth/base.py::OAuth2Provider` holding the shared flow: `redirect_uri`, settings-backed
  `client_id` / `client_secret` (by setting name), `_send` → `ProviderError`, `authorize_url` from
  `authorize_params()`, `_post_token` parsing (`scope_separator`), `exchange_code`, `refresh`.
- Per platform: endpoints, scopes, PKCE method, client-id param name (`client_key` for TikTok),
  extra authorize params (Google `access_type` / `prompt`), client auth style (X basic auth),
  `fetch_identity`, `revoke`. Instagram keeps its Page-selection logic in its own subclass.
- Token handling, `state` checks and storage in `social/` are not touched.

## Verification

- After every stage: `.venv/Scripts/python manage.py test --settings=config.settings.test`
  (397 tests today, all green). Tests mock `platforms.http.transport.requests.request`, so the real
  chunking, retry and resume paths run.
- New tests (Given / When / Then) in `platforms/tests/`: `ResumableState.of` (missing field, wrong
  type, round-trip), `drive` (cancel mid-upload carries state; progress per piece), `http.send` with
  a custom `failure_of`, `fresh_token_on_rejection`.
- Stage 6: existing `test_*_oauth.py` must pass unchanged; `grep` that no token/secret reaches a log.
- Manual: `npm run dev` + uvicorn + worker, connect one account, publish a short video to each
  connected platform, kill the worker mid-upload once and confirm it resumes.
