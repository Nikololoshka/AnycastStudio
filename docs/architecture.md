# Architecture

How a video gets from a person's disk to a platform, and why each piece is
where it is.

---

## The shape

```
Browser (Vite :5173)
  │  SPA + proxy of /api and /admin to Django — one origin
  ▼
Django / uvicorn (:8000) ──► SQLite (WAL)
  │                       └─► Redis (cache, sessions, Celery broker)
  ▼
Celery worker ──► backend/media_files ──► platform APIs
```

Two rules decide most of the layout:

1. **The browser never talks to a platform.** It cannot — CORS forbids it — and
   it should not, because that would mean handing it a token.
2. **Nothing the person is waiting on runs in a request.** An upload takes
   minutes; a request handler has to return in milliseconds.

---

## The four flows

### Signing in

```
GET  /api/auth/csrf    seeds the CSRF cookie
POST /api/auth/login   → session cookie: HttpOnly, SameSite=Lax
GET  /api/auth/me      → the profile, or 401
```

Session cookies rather than a token in storage: the SPA is same-origin, so
cookies plus CSRF are the simple correct answer, and script cannot read the
credential.

### Connecting a platform account

```
POST /api/social/youtube/connect
  → OAuthSession(user, state, encrypted PKCE verifier)
  ← authUrl

window.location = authUrl  →  Google  →  302 back to
GET /api/social/youtube/callback?code&state
  claim(state)                       conditional UPDATE: pending → processing
  state.user == request.user         ← the check that stops account grafting
  exchange_code + fetch_identity
  SocialAccount(tokens encrypted)
  ← 302 /settings/accounts?result=connected
```

The desktop client needed a start/poll dance because it had no browser session.
Here the person is signed in the whole time, so the redirect is enough.

### Uploading

```
POST   /api/media/uploads              declare the file → upload id, chunk size
PATCH  /api/media/uploads/<id>         one piece, with the offset you believe
GET    /api/media/uploads/<id>/status  what the server actually holds
POST   /api/media/uploads/<id>/complete  verify the checksum, keep the file
```

The server is the only authority on the offset. A `PATCH` at the wrong one
answers `409` with the real position instead of appending — which is what makes
resuming safe after a connection drops mid-chunk.

A browser reload loses the `File` handle, so the upload id is kept in browser
storage and the person is asked for the same file again, matched on name and
size, rather than losing what already arrived.

### Publishing

```
POST /api/publications/create  → Publication + one PublicationTarget per platform
                               → run_target.delay(...) on commit
                                 ══ the tab can close here ══

worker: claim → validate → upload → publish
        progress and resume point written to the target row
browser: GET /api/publications/<id> every 2s while isActive
```

Scheduling is the platform's job. A video due later is uploaded private with a
`publishAt`, and YouTube publishes it. That is why there is no scheduler table
here — the desktop client needed one only for platforms that lack this.

---

## Why these choices

### No Django REST Framework

`common/responses/` already defines the contract — a `status` string with the
HTTP code derived from it — and `common/guard.py::guard` builds both sync and
async wrappers from one check. `APIView` is sync-only, so an async endpoint
would live outside it and split the codebase into two conventions. There is one
client, no browsable API, and the types are mirrored in TypeScript anyway.
pydantic covers what was actually missing: request-body validation.

### Polling, not server-sent events

Two seconds of latency on a progress bar costs nothing. A stream would mean an
async view, a pub/sub channel, keepalives and proxy buffering rules for the
same picture. RTK Query turns polling into one line of configuration.

### A custom chunked protocol, not tus or S3

The Django tus implementations are unmaintained, and `tusd` is a fourth service
with its own auth wiring. Presigned S3 still leaves the worker to download the
whole file to feed the platform's own chunk API. `media/storage.py` is the only
place a path is built, so moving to object storage later is one module.

### SQLite

The web process and the worker share one file. It works because of WAL,
`busy_timeout` and `transaction_mode=IMMEDIATE`, and because no transaction is
ever held open across a call to a platform. There is no
`SELECT ... FOR UPDATE SKIP LOCKED`, so work is claimed with a conditional
UPDATE — a pattern that ports to PostgreSQL unchanged. The trigger for moving
is `database is locked` in the worker log.

---

## Resilience

| What fails | What happens |
| --- | --- |
| Connection drops mid-chunk | The client asks for the offset and continues |
| Browser reloads mid-upload | The person re-picks the same file; the server's bytes are kept |
| Worker dies mid-upload | `resume_state` holds the session URI and offset; the retried task continues |
| Token expires mid-upload | Google answers 401, the pipeline refreshes and resumes from the confirmed offset |
| Task delivered twice | The claim is a conditional UPDATE; the second delivery finds nothing to take |
| Platform is down | Five attempts, exponential backoff with jitter, then the target fails with a reason |
| Platform rejects the file | Failed immediately, never retried — repetition burns quota and changes nothing |

---

## Adding a platform

1. `backend/platforms/<platform>/` — `oauth.py`, `upload.py`, `publish.py`,
   `settings.py`, `capabilities.py`. No imports from another platform folder.
2. Register the provider in `social/providers.py` and the capabilities in
   `publishing/views/platforms.py`.
3. Teach `publishing/pipeline.py` to dispatch on the target's platform.
4. Add the settings panel and the `AVAILABLE_PLATFORMS` entry in the frontend.

The three platforms that left the tree during the migration are in the
`v0-desktop` tag, along with the Rust upload loops that document each one's
protocol. Three defects in that code must be fixed while porting rather than
carried over: X does not poll `STATUS` after `FINALIZE`, Instagram does not
poll the container status before `media_publish`, and TikTok's `publish()`
reports success unconditionally.
