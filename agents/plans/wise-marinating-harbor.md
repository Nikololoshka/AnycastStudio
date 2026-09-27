# Typed platform responses instead of `json_dict`

## Context

`platforms/http/body.py::json_dict` turns every platform answer into a plain `dict`, and about 110 call
sites dig into it with `.get(...)`, `isinstance(...)`, `str(... or "")`, `int(...)`. The shape of each
answer lives only in those scattered lookups: a typo in a key is silent (it just becomes `""`), the
same defensive code repeats per platform, and nothing documents what we actually rely on. The TODO in
`body.py` asks for a native structure per response.

Goal: every answer we read is parsed once, at the edge, into its own model; the rest of the code works
with typed attributes. Behaviour stays the same, including the refusal messages people see.

## Approach

**pydantic 2** — already a dependency (`requirements.txt`, used by `common/request_body`), works in the
plain `platforms/` package (no Django), gives aliases, coercion and nested models. No new dependency.

### 1. One parsing entry point — `platforms/http/body.py`

```python
def parse(response, model: type[M], *, label: str, refusal: str | None = None) -> M
```

- `model.model_validate(response.json())`.
- Not JSON or `ValidationError` → `PlatformFailure(PLATFORM, refusal or f"{label} answered in an unexpected shape", details=<field paths only>)`.
- **Never** put `ValidationError` text or input values in the message, details or a log: token
  responses carry `access_token` / `refresh_token`. Only `error["loc"]` paths go out.
- Base model `PlatformModel(BaseModel)`: `model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)`.
  Lenient by default: fields we only display get defaults; fields we cannot continue without are
  required, and the call passes the existing domain message as `refusal`
  (e.g. `"X did not open an upload"`), so people see the same text as today.
- `json_dict` / `message_of` stay only for the generic error-message extraction in `failures.classify`,
  where the body shape is unknown by design.

### 2. Models per platform — `platforms/<p>/responses.py`

Wire shapes only, named after what they are, with aliases for the platform's field names:

- **YouTube**: `TokenAnswer` (shared shape, lives in `platforms/oauth/`), `ChannelList` → `Channel` →
  `Snippet` / `Thumbnails`, `UploadedVideo(id)`.
- **TikTok**: generic `Envelope[T]` with `error: EnvelopeError(code="ok", message)` and `data: T`
  (replaces `data_of`); `InitData(publish_id, upload_url)`, `StatusData`, `CreatorData`, `UserInfo`.
- **X**: `Problem` (type/detail/title) for `failure_of`, `Data[T]`, `MediaInit(id)`, `ProcessingInfo`
  (state, error), `CreatedPost(id)`, `User`.
- **Instagram**: `GraphError` (code, error_subcode, message, error_user_msg) for `failure_of`,
  `Created(id)`, `ContainerStatusAnswer` (status_code, status, video_status.uploading_phase.bytes_transferred),
  `Page`, `PageList`, `DebugToken` (granular_scopes, user_id), `Permalink`.

Where a hand-written dataclass today is just "the answer plus properties" (`ContainerStatus`,
`ProcessingStatus`, `PublishStatus`, `CreatorInfo`), it **becomes** the pydantic model — properties such
as `is_ready` / `is_failed` stay on it, one layer instead of two. `CreatorInfo.as_json()` keeps its
camelCase output via `model_dump(by_alias=...)` or stays explicit.

### 3. Call sites

Each `json_dict(...)` + `.get` chain becomes `parse(response, Model, label=LABEL, refusal=...)` and
attribute access. Platform `call(...)` helpers return a parsed model when given one:
`call(method, path, token, model=Created, refusal="Instagram did not open an upload")`.

Order, one commit each, tests green after every step:

1. `parse` + `PlatformModel` + tests (`platforms/tests/test_http_parse.py`).
2. OAuth token answers (`platforms/oauth/base.py::_post_token`, Instagram `_user_token`) — sensitive
   area, same rule as before: nothing from the body in logs.
3. YouTube → TikTok → X → Instagram, one platform per commit.
4. Remove `data_of` helpers and the TODO; `json_dict` stays private to `failures`.

## Critical files

- `backend/platforms/http/body.py`, `backend/platforms/http/__init__.py`
- `backend/platforms/oauth/base.py`
- `backend/platforms/<p>/{api,upload,status,oauth}.py`, new `backend/platforms/<p>/responses.py`
- `backend/platforms/tiktok/creator_info.py`
- Docs: `docs/platforms/adding-a-platform.md` (add `responses.py` to the file table), CLAUDE.md shape list.

## Verification

- `.venv/Scripts/python manage.py test --settings=config.settings.test` after each commit (419 today).
  Existing tests feed JSON through `FakeResponse`, so they exercise the new parsing unchanged.
- New tests (Given / When / Then): unexpected shape → `PLATFORM` failure with the domain message;
  a token answer with a missing field → the refusal names no token value (assert the secret string is
  absent from message and details); extra fields are ignored; numeric strings coerce (`bytes_transferred: "1024"`).
- Manual: connect and publish once per platform after the last commit.
