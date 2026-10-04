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

The Rust loops are the specification for chunk sizes and retries.
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

Everything goes in `backend/platforms/<p>/`. Nothing in `publishing/` or
`social/` changes: the pipeline, the confirmation polling, the token refresh
and the OAuth flow are shared use cases in `services/usecases/` and reach
the platform only through its `Platform`. Read
`docs/adr/0002-platforms-core.md` and `docs/adr/0003-async-platforms.md` for
why.

### The shape, mirrored from `platforms/tiktok/`

```text
<p>/
├─ core/                  <p>_config.py (<P>Config, frozen, with `configured`),
│                         <p>_endpoints.py, <p>_http.py (<P>Http(PlatformHttp)),
│                         <p>_response.py (<P>Response(PlatformResponse)),
│                         <p>_answer.py (the pydantic base of every answer)
├─ auth/                  <p>_authorization_interactor.py, answers/
├─ publish/               <p>_publish_interactor.py, <p>_options.py, answers/
├─ <p>_capabilities.py    <P>Capabilities(PlatformCapabilities)
├─ <p>_validator.py       <P>Validator(PlatformValidator)
└─ <p>_platform.py        <P>Platform(Platform)
```

`platforms/tests/core/test_architecture.py` fails if a folder misses a part,
imports another platform or Django, or exposes a public function.

### The parts

- **Http and response.** `PlatformHttp.request` sends and reports a network
  error by its class only; `answer(method, url, Model)` reads the body into a
  pydantic answer or raises. `<P>Response.failure()` maps the platform's error
  envelope — even on a 200 — onto a `PlatformFailure`, and `refusal()` keeps
  the platform's words for the message. Never read an answer as a raw dict.
- **Authorization interactor.** `create_auth_request(state)` builds the consent
  URL and the PKCE verifier without a network call; `create_auth_token`,
  `refresh_auth_token`, `fetch_auth_profile` and `revoke_auth_token(AuthToken)`
  talk to the platform. Revoke receives the whole token: the platform decides
  what it revokes.
- **Publish interactor.** Works on a `PublishJob`:
  - `upload(job, token)` — an async generator of `UploadProgress`; the last
    event carries the media id. Read the file through `VideoFile.piece`, and
    retry a chunk that met an outage through `RetryPolicy`. Nothing about the
    session is stored.
  - `publish(job, token)` — `Published` or `Scheduled` when the platform
    answers at once, `AwaitingConfirmation(state)` when it processes later;
  - `confirm(job, token)` — `NotReady`, `Published`, or `ReadyToCommit` when
    the last step must not run twice; then implement `commit(job, token)`,
    and `resolve_uncertain` if the platform can tell whether an unanswered
    commit went through.
- **Validator.** `validate(draft, media)` returns error codes the frontend also
  knows. `draft.caption()` is the shared title + description + hashtags text.
- **Platform.** Builds one `<P>Http` on the session it receives and hands it to
  every part.

### Registrations

- `platforms/platform_catalog.py` and `platforms/platform_configs.py` — the
  platform and its config; `platforms/core/platform_type.py` — its name.
- `services/wiring.py::Container.platform_configs` — the config built from the
  `<P>_CLIENT_*` settings and the callback URL.
- `config/settings/base.py` and `test.py` — `<P>_CLIENT_*`; `.env.example` —
  the block with the redirect URI and the required app type.

### Scheduling

Pick the capability honestly:

- `native` — the platform publishes at a time we send (YouTube).
- `deferredUpload` — it cannot. The target stays `queued`, and
  `DeferredDispatcher` starts the upload at `publish_at` (TikTok, Instagram,
  X). It finds these platforms through their capabilities.
- `stagedPublish` — upload early and publish later. It is **not implemented**
  on the server. Before choosing it, check how long the platform keeps an
  unpublished upload; if that is shorter than the scheduling horizon, use
  `deferredUpload`.

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

- **Platform**, `backend/platforms/tests/<p>/` on the `FakeSession` from
  `platforms/tests/fakes/http.py`: the init body matches the chunks sent,
  every byte goes once and in order, the last-chunk rule, a chunk retried
  after an outage, 401 → `token_rejected`, the envelope error on a 200, each
  refusal reason mapped to its `PlatformFailure`.
- **Pipeline**, `backend/publishing/tests/test_<p>.py` through
  `container().run` with a stateful double routed by URL
  (`FakeSession.responder`): local refusals make no call, an upload ends
  `processing` rather than `completed`, confirmation completes, fails with the
  platform's reason, or times out, a duplicate confirmation does nothing, and
  the abandoned-target sweep leaves `processing` alone.
- **OAuth**, `backend/social/tests/test_<p>.py`: the consent URL (client
  parameter name, challenge encoding) and a full callback.
- **Contract**: add a test to `publishing/tests/test_platforms.py::ContractScenarios`
  with `frontend_defaults(...)` and `backend_defaults(<P>Options.of({}))`.

---

## What TikTok changed in shared code

Historical: these changes predate `docs/adr/0002-platforms-core.md` and
`docs/adr/0003-async-platforms.md`, which moved them into `platforms/core/`.

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

## Notes on the ported platforms

Read from the desktop code; check each one against the platform's current
documentation before relying on it.

**X** — ported; what was decided is in `docs/platforms/x.md`. The desktop's
`command=INIT/APPEND/FINALIZE` upload is retired by X; the port uses
`/2/media/upload/initialize`, `/{id}/append` and `/{id}/finalize`.

**Instagram** — ported; what was decided is in `docs/platforms/instagram.md`.

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
