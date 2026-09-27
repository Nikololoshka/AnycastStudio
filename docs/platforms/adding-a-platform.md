# Adding a platform

How TikTok was ported from the `v0-desktop` tag, written so X and Instagram can
follow the same path. `docs/platforms/tiktok.md` has the TikTok specifics;
this file has the shape every platform shares and what TikTok taught.

---

## Where the old code is

Everything the desktop client did is in the `v0-desktop` tag. Read it with
`git show v0-desktop:<path>`; never check it out.

| Platform | Auth and settings | Upload loop |
| --- | --- | --- |
| X | `frontend/src/platforms/x/` | `frontend/src-tauri/src/commands/x_upload.rs` |
| Instagram | `frontend/src/platforms/instagram/` | `frontend/src-tauri/src/commands/instagram_upload.rs` |

The Rust loops are the specification for chunk sizes, retries and resume.
The TypeScript auth code is not a model to copy: it ran in the browser with
the client secret in the bundle. Those secrets are compromised; every platform
gets a new client pair before it is connected again.

---

## The order that worked

Six commits, each with its tests, each reviewed before the next:

1. What the platform needs from shared code, one change at a time, with
   YouTube behaving exactly as before.
2. `backend/platforms/<p>/`, the publisher, the registrations, the tests.
3. The frontend module, the locales, the contract test, the docs.

Shared changes first, so the platform commit only adds files and one line per
registry.

---

## Backend

### `backend/platforms/<p>/` — the platform's API, nothing else

A plain package: no Django models, no imports from a sibling platform. Mirror
`platforms/tiktok/`:

| File | Holds |
| --- | --- |
| `api.py` | `send` and `call` over `platforms.http` (retry, timeout, classification), plus the platform's error envelope |
| `oauth.py` | the `PlatformProvider`: `name`, `scopes`, `uses_pkce`, `redirect_uri` (use `oauth.callback_url`), `code_challenge`, `authorize_url`, `exchange_code`, `refresh`, `fetch_identity`, `revoke(access_token, refresh_token)` |
| `upload.py` | the upload loop and its `ResumeState` (`as_dict`, `of`) |
| `status.py` | the status query for an asynchronous publish, and the refusal reasons mapped to failure types |
| `video_options.py` | `VideoOptions`, `video_options_of(raw)` (lenient: unknown values fall back), `as_json()` in camelCase |
| `capabilities.py` | `capabilities()` and `validate(...) -> ValidationResult` with error codes the frontend also knows |
| `errors.py` | `Cancelled(state)` and `NeedsFreshToken(state, message)` |

Rules that held:

- Every request goes through `platforms.http`. Report the class of a network
  exception, never its text.
- A 401 raises `NeedsFreshToken` carrying the resume state. The pipeline
  refreshes once and resumes.
- Never retry what the platform decided about. Only network errors, 5xx and 429
  are retried, and that happens in `with_retry`.
- Check the error envelope even on 200. TikTok puts
  `{"error": {"code": ...}}` in successful responses; Meta and X have their own
  shapes. Keep the platform's code in `PlatformFailure.details`.

### `backend/publishing/publishers/<p>.py` — the platform as the pipeline sees it

A module with:

- `capabilities` — the platform's function;
- `validate(target) -> ValidationResult` — local checks, before any call;
- `upload(target, access_token, resume, on_progress, should_cancel) -> media_id`
  — translates the platform's `Cancelled` and `NeedsFreshToken` into
  `publishers.outcome`, and reports progress with `state.as_dict()`;
- `publish(target, media_id, access_token) -> Published` — `completed` or
  `scheduled` when the platform answers at once. Return `processing`, with a
  `resume_state` holding `confirming_since` and `polls`, when it answers later;
- `confirm(target, access_token) -> Published | None` — only for an
  asynchronous publish: `None` means ask again later, and a refusal raises.

Register it in `publishing/publishers/__init__.py`. The pipeline, the retry
after a 401, the progress writes, the claim, the confirmation polling and the
deadline are shared and need no change.

### Registrations

- `social/providers.py` — the provider.
- `publishing/views/platforms.py` — the capabilities.
- `config/settings/base.py` and `test.py` — `<P>_CLIENT_*`; `.env.example` —
  the block with the redirect URI and the required app type.

### Scheduling

Pick the capability honestly:

- `native` — the platform publishes at a time we send (YouTube).
- `deferredUpload` — it cannot. The target stays `queued`, and the beat sweep
  starts the upload at `publish_at` (TikTok). Nothing else is needed: the sweep
  finds deferred platforms through their capabilities.
- `stagedPublish` — upload early and publish later. The desktop used it for X
  and Instagram. It is **not implemented** on the server. Before choosing it,
  check how long the platform keeps an unpublished upload; if that is shorter
  than the scheduling horizon, use `deferredUpload`.

---

## Frontend

`frontend/src/platforms/<p>/`, mirroring `platforms/tiktok/`:

- `settings.ts` — the settings type, `<P>_DEFAULT_SETTINGS` (the contract test
  parses this block, so keep it a flat literal), the option lists, the
  normalizer;
- `<P>Descriptor.ts` — the capabilities copy and `validate(draft)` returning
  `DraftError` codes; add new codes to `PlatformDescriptor.ts` and to
  `composer.summary.invalid` in both locales;
- `<P>SettingsPanel.tsx` — HeroUI components through `SettingSelect`,
  `SettingSwitch` and `SettingNumber`;
- `settings.test.ts` — the pure functions only.

Registrations: `AVAILABLE_PLATFORMS` in `domain/platform/order.ts`,
`platforms/registry.ts`, `platforms/settings.ts`, and
`features/composer/PlatformTab.tsx`. The glyph and brand colour already exist
for X and Instagram.

The Publish button already refuses on any selected platform's `validate`
errors and names a selected platform without a connected account.

Locales: `en` and `ru` together, in `platforms.json` under the platform's key.

---

## Tests that caught real mistakes

- **Platform**, `backend/platforms/tests/test_<p>_*.py` with a stateful double
  routed by URL: the init body matches the chunks sent, every byte goes once
  and in order, the last-chunk rule, resume inside and outside the upload
  URL's lifetime, 401 → `NeedsFreshToken`, the envelope error on a 200, each
  refusal reason.
- **Pipeline**, `backend/publishing/tests/test_<p>.py`: local refusals make no
  call, an upload ends `processing` rather than `completed`, confirmation
  completes, fails with the platform's reason, or times out, a duplicate
  confirmation does nothing, and the abandoned-upload claim leaves
  `processing` alone.
- **OAuth**, `backend/social/tests/test_<p>.py`: the consent URL (client
  parameter name, challenge encoding) and a full callback.
- **Contract**: add a test to `publishing/tests/test_platforms.py::ContractScenarios`
  with `frontend_defaults(...)` and `backend_defaults(...)`.

---

## What TikTok changed in shared code

Already done; X and Instagram use it as it is.

| Change | Why |
| --- | --- |
| `publishing/publishers/` registry | the pipeline called YouTube directly |
| `deferredUpload` via `dispatch_due_targets` | platforms without native scheduling |
| `confirm_target` and the `processing` state | the desktop reported success before the platform decided |
| refresh lease on `SocialAccount` | X and TikTok rotate refresh tokens |
| `PlatformProvider.code_challenge` | TikTok's PKCE is hex, not base64url |
| `revoke(access_token, refresh_token)` | Google revokes by refresh token, TikTok by access token |
| `PUBLIC_REDIRECT_ORIGIN` | platforms that accept only an HTTPS redirect, tested through a tunnel |
| `GET /api/social/accounts/<id>/creator-info` | TikTok's audit requires the creator's options before posting |

---

## Notes for the next two

Read from the desktop code; check each one against the platform's current
documentation before relying on it.

**X**

- OAuth 2 with standard S256 PKCE (`s256_challenge`), scopes
  `tweet.read tweet.write users.read media.write offline.access`. The refresh
  token rotates, and the lease covers that.
- Upload: `POST https://api.x.com/2/media/upload` with `INIT`, `APPEND`
  (`segment_index`, 5 MiB), `FINALIZE`. The desktop did not poll `STATUS`
  after `FINALIZE` — fix it by polling processing in `upload` before the post
  is created, or in `confirm`.
- Desktop limits: 512 MiB. No native scheduling.

**Instagram**

- Facebook Login with a Page linked to an Instagram professional account. The
  desktop reads `me/accounts` and `debug_token` granular scopes to find the IG
  user. Meta issues long-lived tokens instead of refresh tokens, so `refresh`
  and the refresh margin need thought before porting.
- Upload: a Reels container via `graph.facebook.com/v23.0`, resumable upload
  to `rupload.facebook.com/ig-api-upload/v23.0` with an `offset` header, 4 MiB
  chunks. No public video URL is needed. The desktop did not poll the
  container status before `media_publish` — that belongs in `confirm` or in
  `publish`.
- Desktop limits: 1 GiB. No native scheduling.

---

## Running it

- Restart the worker and beat after every backend change. Celery does not
  reload, and a stale worker runs the old pipeline — with TikTok that sent a
  TikTok token to YouTube.
- A platform that accepts only an HTTPS redirect is tested with
  `PUBLIC_REDIRECT_ORIGIN` and `ngrok http 8000`; see
  `docs/platforms/tiktok.md`.
