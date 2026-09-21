# 1. Move from a Tauri desktop client to a web application

Date: 2026-09-21
Status: accepted

## Context

AnycastStudio began as a Windows desktop client built with Tauri: React and
Redux Toolkit in the webview, Rust for the filesystem, the OS keyring, a
loopback OAuth listener and four chunked upload loops. A small Django service
existed alongside it for one job only — running the Facebook/Instagram OAuth
dance on the app's behalf, because that provider cannot redirect to a loopback
address.

That shape has three limits we care about. Publishing stops when the machine
sleeps or the app closes. Platform client secrets ship inside the bundle.
Scheduled publishing only fires if the app happens to be running.

We want a web application: the browser collects the video and the metadata, the
server owns the tokens, the files and the publishing.

## Decision

### Product

- Multi-user architecture, but a **closed circle** of users. No platform audits
  are pursued for now, so the quota and privacy ceilings of unaudited apps apply.
- **No self-service registration and no email.** Accounts are created through the
  Django admin, which is never published — it is reached over an SSH tunnel.
- **YouTube only** in the first release. The X, Instagram and TikTok code is
  removed from the working tree and recovered from the `v0-desktop` tag when
  each platform is ported.
- One connected account per platform, enforced in the service layer. The schema
  allows several so that lifting the limit is a UI change.
- **Scheduling uses the platform's own mechanism.** For YouTube that is
  `privacyStatus: private` plus `status.publishAt`. The desktop's local
  scheduler, the staged-publish planner and the `ScheduledJob` table are not
  ported yet; they exist only to serve platforms without native scheduling.
- The composer keeps its split between shared fields and per-platform tabs. A
  publications list exists so a result is visible after the tab was closed.

### Technical

- **Extend the existing Django project** rather than start a new backend. Its
  provider registry, its `{"status": ...}` response contract, its `guard()`
  decorator factory and its conditional-UPDATE session claim are the seams the
  rest is built on.
- **No Django REST Framework.** `views/common.py` already defines the response
  contract, and its `guard()` builds sync *and* async wrappers from one check —
  `APIView` is sync-only. Request bodies are validated with pydantic instead.
- **SQLite**, with WAL, `busy_timeout` and `transaction_mode=IMMEDIATE`. The
  move to PostgreSQL is prepared (`DATABASE_ENGINE`, portable ORM usage) and is
  triggered by `database is locked` appearing in the worker log.
- **Session cookies, not JWT.** The SPA is served same-origin through the Vite
  proxy, so cookies plus CSRF are the simple correct answer, and an
  `EventSource` could authenticate with them if server-sent events are ever
  added — it cannot send an `Authorization` header.
- **Celery with Redis.** Uploads run for minutes and must survive the tab
  closing and the worker restarting. Redis runs from a plain `docker run`; the
  repository carries no Dockerfile, compose file or nginx config.
- **Polling, not server-sent events**, for upload progress. One line of RTK
  Query configuration against an async view, a pub/sub channel and proxy
  buffering rules.
- **A custom chunked upload protocol** between browser and server, mirroring the
  Google resumable protocol the desktop already implemented. Not tus (the Django
  implementations are unmaintained), not presigned S3 (the worker must read the
  whole file anyway to feed the platform's chunk API).
- Platform tokens are encrypted at rest with `MultiFernet` under keys that are
  separate from `DJANGO_SECRET_KEY` and rotatable.
- Tauri is removed entirely. There is no desktop build to maintain.

### Operations

- The first release **runs locally only**. Deployment, TLS, nginx, backups and
  log rotation are out of scope. The OAuth redirect URI is
  `http://localhost:5173/api/social/youtube/callback`; Google permits
  `http://localhost` on any port for a client of type "Web application".

## Consequences

- The Vite dev server becomes part of the OAuth path: the redirect lands on its
  port and is proxied to Django. Deploying later means re-registering the URI.
- The YouTube Data API allows roughly six `videos.insert` calls a day on the
  default quota, for the whole project rather than per user. Failed publications
  are therefore never retried automatically; a person presses the button.
- The client secrets that shipped in the desktop bundle are treated as
  compromised and rotated.
- Roughly 2,000 lines of Rust and three working platform integrations leave the
  working tree. They are preserved under the `v0-desktop` tag, and the Rust
  upload loops remain the specification for the Python ports — including the
  chunk sizes, the retry policy and the resume semantics.
- Three known defects must be fixed while porting, not carried over: X does not
  poll `STATUS` after `FINALIZE`, Instagram does not poll the container status
  before `media_publish`, and TikTok's `publish()` reports success
  unconditionally.
