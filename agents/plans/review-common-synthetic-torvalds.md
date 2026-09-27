# Review: backend/platforms

## Context

Next module in the bottom-up backend review (config, common, accounts done).
`platforms/` is a plain package: `base.py` (shapes), `http.py` (transport,
classification, retry), `pkce.py`, `youtube/{oauth,capabilities,settings,publish,upload}.py`.
`social` calls the OAuth side, `publishing/pipeline.py` the upload/publish side.
Goal: fix the defects found, make the error vocabulary and the module names
obvious, and drop comments/docstrings (Code Style), keeping the protocol
knowledge in a README. All 841 lines and their callers were read.

## Findings — fix

1. **A transient failure during token refresh forces a reconnect.**
   `YouTubeProvider._post_token` (`youtube/oauth.py:64`) calls `request` once:
   a network blip or a Google 5xx raises `ProviderError`, and
   `social/services.py::get_valid_access_token` answers it with
   `_mark_needs_reauth`. The person must reconnect for Google's outage.
   Fix: send the token, identity and revoke calls through `with_retry` like
   upload/publish do; only a 400/401 (`invalid_grant`) is a real refusal.
   Map the final failure back to `ProviderError` so `social` is unchanged.
   *(Sensitive: `platforms/*/oauth.py` — approving the plan is the approval.)*

2. **Resuming at `offset == size` crashes.** `youtube/upload.py:141-177`: if the
   stored offset already equals the size (worker died after the last chunk,
   before the id was read), the loop never runs and `response` is unbound →
   `UnboundLocalError`.

3. **A resumed upload trusts a stale offset.** `resume_state` is written only on
   whole percents (`publishing/pipeline.py:148`), so after a crash the stored
   offset lags Google's by up to 1 % (≈ 40 MB of 4 GB). Google's protocol is to
   ask first: `PUT session_uri` with `Content-Range: bytes */{size}` → 308 +
   `Range`, or 200/201 with the video when complete.
   Fix for 2 and 3 together: `upload()` starts a resumed session with that
   status query, takes the offset from it, and returns the id directly when
   Google already has the whole file.

4. **308 without a `Range` header is read as "the whole chunk landed".**
   `confirmed_offset(response, fallback=offset+len(piece))` (`upload.py:110`).
   Per Google's protocol, no `Range` means no bytes were persisted; the next
   chunk would be sent at the wrong offset. Fix: on 308, no `Range` → offset 0;
   the fallback applies only to a completed (200/201) response.

5. **`fetch_identity` crashes on a string `error`.** `oauth.py:114`
   `(body.get("error") or {}).get("message")` → `AttributeError` when Google
   answers `{"error": "invalid_token"}`. Use `http.message_of`, as upload does.

6. **Error vocabulary is half constants, half literals.** `upload.py` raises
   `PlatformFailure("platform", …)` and `PlatformFailure("file", …)`; `"file"`
   has no constant in `http.py` although the frontend's `ErrorType` has it.
   Fix: add `FILE`, use the constants everywhere.

## Findings — structure and naming

7. **`youtube/settings.py` collides with `django.conf.settings`**, which is why
   every caller writes `settings_`. Rename the module to
   `youtube/video_options.py`, `YouTubeSettings` → `VideoOptions`,
   `settings_of` → `video_options_of`, parameters `settings_` → `options`.
   Callers: `publishing/pipeline.py`, `publishing/tests/test_api.py`
   (contract test), `youtube/{capabilities,publish,__init__}.py`.
8. **Two error classes with blurry roles.** Keep both, make the split explicit
   by name: `ProviderError` (OAuth: message safe to show) stays in `base.py`;
   `PlatformFailure` (classified publish failure) stays in `http.py`. After
   fix 1, `request()` no longer raises `ProviderError` for network errors —
   it raises `PlatformFailure(NETWORK, retryable=True)`, and `with_retry` stops
   translating.
9. **`Capabilities.scheduling: str  # native | …`** → `Literal[...]` type; the
   comment goes.
10. Unused/odd: `upload.__all__` re-exports `ProviderError`; unreachable
    `raise last` at the end of `with_retry`; `"YouTube"` label spelled in
    three places → one `LABEL` in `youtube/__init__` scope (`oauth` keeps
    `label="Google"` for the Google endpoints).

## Comments and docstrings

Remove all, per Code Style. The protocol knowledge that the code cannot carry
moves to a new `backend/platforms/youtube/README.md`:
- `access_type=offline` + `prompt=consent` are what make Google issue a
  refresh token; Google omits it on refresh (`TokenBundle.merged_with`).
- `publishAt` is ignored unless `privacyStatus` is `private`.
- Resumable upload: `Location` session, `Content-Range`, 308 + `Range`, status
  query `bytes */size`, no `Range` = nothing persisted.
- Retry policy: 5 attempts, 1–30 s backoff with jitter; 401/403/4xx never
  retried because each attempt spends quota.
- Why tokens never appear in exception text (`request` reports the class only).

`backend/platforms/README.md` gets the package rules now in `base.py`'s
docstring (not a Django app, no model imports, no imports between platforms).

## Tests

Add `backend/platforms/tests/` (mocked at `platforms.http.requests.request`,
as CLAUDE.md requires):
- `test_upload.py`: resume starts with a status query and uses its offset;
  resume when Google already has everything returns the id without sending;
  308 without `Range` resends from 0; 308 with `Range` wins over arithmetic
  (move the existing scenario here only if it is platform-level).
- `test_oauth.py`: refresh survives one 503 then succeeds; `invalid_grant`
  is not retried and raises `ProviderError`; identity with a string `error`
  raises `ProviderError`, not `AttributeError`.
- Existing pipeline/social tests stay and must pass unchanged in behaviour.

## Verification

```bash
cd backend
.venv/Scripts/python manage.py test --settings=config.settings.test
.venv/Scripts/python manage.py test platforms --settings=config.settings.test
.venv/Scripts/python manage.py check
grep -rn "settings_\b\|YouTubeSettings\|settings_of" --include=*.py .   # nothing left
```

Commit when asked: `fix: make YouTube uploads and token refresh survive interruptions`
plus a `refactor:` for the renames if you want them separate.
