# AnycastStudio

Web application for publishing one video to several platforms from a single
composer. Django + Celery on the server, React SPA in the browser.

---

## Purpose

This file is the operating manual for AI agents working in this repository. It
should give an agent enough context to understand what the project does, follow
its conventions, put code in the right place, run the right commands, and know
when to stop and ask a person.

---

## Project Snapshot

- Project type: web application, run locally for now
- Primary users: a closed circle — a couple of people publishing their own videos
- Domain: multi-platform video publishing
- Maintainers: solo developer project
- Default branch: `master`

### What is in scope today

**YouTube, TikTok and Instagram.** The X integration was written for the
desktop client and removed from the working tree during the web migration. It
is recoverable from the `v0-desktop` tag.

There is **no self-service registration and no email**. Accounts are created
through the Django admin, which is never published — it is reached over an SSH
tunnel. Deployment, TLS and backups are out of scope while the app runs locally.

Decisions behind all of this are recorded in `docs/adr/0001-web-migration.md`.
Read it before proposing a different architecture.

---

## Agent Principles

Unless asked otherwise:

- prefer the smallest safe change that solves the task;
- preserve existing architecture and naming conventions;
- respect the dependency direction (see Architecture);
- verify work before finishing (tests, typecheck, lint, run it when relevant);
- avoid speculative refactors;
- ask before destructive, irreversible, or scope-expanding operations.

### Optimize For

1. Correctness
2. Maintainability
3. Speed

### Never Do These By Default

- Rewrite architecture without being asked.
- Introduce a new dependency when an existing one can solve the problem.
- Put publishing logic, tokens or platform API calls in the browser — they
  belong on the server.
- Add comments or docstrings (see Code Style).
- Guess around OAuth, token storage, or credential handling (see Security).

---

## Tech Stack

### Core Stack

- Language(s): Python 3.13, TypeScript 6.0
- Runtime(s): Node.js 24, uvicorn (ASGI)
- Framework(s): Django 5.2, React 19.1, Redux Toolkit 2.12
- Package manager(s): pip, npm
- Build tool(s): Vite 8, tsc
- Database: SQLite, with WAL (see SQLite below)
- Messaging / queueing: Celery 5.6 over Redis
- Cache / storage: Redis for the cache and sessions; uploaded video on disk
  under `backend/media_files/`
- Hosting: none yet — `docker run` for Redis, everything else runs locally

### Key Libraries And Services

| Area | Library | Purpose | Notes / Constraints |
| --- | --- | --- | --- |
| API | plain Django views | HTTP layer | No DRF. `common/responses/` is the contract, `common/access/` and `common/rate_limit/` the decorators |
| Validation | pydantic 2 | Request bodies | Through `common/request_body::validate` |
| Queue | celery[redis] 5.6 | Background uploads | `acks_late`; no task-level retry, the pipeline decides |
| Encryption | cryptography | Platform tokens at rest | `MultiFernet`, rotatable; see `common/encryption/` |
| Passwords | argon2-cffi | Hashing | First in `PASSWORD_HASHERS` |
| HTTP (server) | requests | Platform calls | Only through `platforms/http/` |
| Config | python-dotenv | Reads `backend/.env` | Real env vars win |
| UI | HeroUI 3 | Component library | Compound components; built on React Aria |
| Styling | Tailwind CSS 4.3 | Utilities and theme tokens | Tokens defined in `src/styles.css` |
| Server state | RTK Query | Everything the server owns | Ships inside `@reduxjs/toolkit`, not a new dependency |
| Routing | react-router 7 | SPA routes | Data router in `src/app/router` |
| i18n | i18next / react-i18next | English and Russian | Keys typed from the `en` resources |
| Icons | lucide-react, simple-icons | UI and brand marks | Brand marks only through `components/PlatformGlyph` |
| Animation | motion 13 | Transitions | `MotionConfig reducedMotion="user"` |
| Tests | Django TestCase, Vitest | | See Testing |

### Version Policy

- Version source of truth: `backend/requirements.txt`, `frontend/package.json`
- Dependency update policy: manual

---

## Architecture

Layered on both sides, with the same dependency direction:

```
Browser (Vite SPA)
  │  session cookie + CSRF, same origin through the Vite proxy
  ▼
uvicorn / Django ──► SQLite (WAL)
  │                └► Redis (cache, sessions, Celery broker)
  ▼
Celery worker ──► backend/media_files ──► platform APIs
```

Server: `views → services → platforms/<p> → the platform's API`.
Browser: `components → RTK Query hooks → the API`.

**Business logic lives on the server.** The SPA renders, collects input and
reports progress. Publishing, scheduling and tokens are the server's.

### Architectural Rules

- A platform adapter (`backend/platforms/<p>/`) is called only from
  `publishing/services`, `publishing/pipeline` or a Celery task — never from a
  view. A view returns in milliseconds; an upload takes minutes.
- `backend/platforms/` is a plain Python package, not a Django app. It must not
  import models, so a task can use it directly. Each platform folder is
  self-contained: no imports between `platforms/youtube` and its future
  siblings.
- Every platform implements `PlatformProvider` for OAuth and the upload/publish
  functions its own module exposes; `platforms/oauth/` and
  `platforms/capabilities/` hold the shapes.
- Every platform HTTP call goes through `platforms/http/`, which owns the
  timeout, the error classification and the retry policy.
- Server state in the browser belongs to an RTK Query endpoint in `src/api/`.
  Only genuinely client-owned state goes in a slice: the composer draft, the
  in-flight browser upload, the theme and the language.
- UI components call RTK Query hooks, never `fetch` directly. The one exception
  is `services/upload/chunkedUpload.ts`, a long-running transfer that a cache
  layer does not help with.
- Build UI from HeroUI components before writing custom markup; style with
  Tailwind utilities, not inline `style` objects or per-component CSS.
- Colours, spacing and fonts come from the theme tokens (`bg-surface`,
  `text-muted`, `text-accent`, `font-display`, …). Add a token to
  `src/styles.css` for both light and dark rather than hardcoding a hex value.
- Light and dark are driven by the `dark` class on `<html>`, set by `ThemeSync`
  in `app/providers` from `settings.theme`.
- UI text goes through `useTranslation` and the JSON resources in
  `src/locales/<lang>/`. Never hardcode a user-visible string. Keep `en` and
  `ru` in sync — the keys are typed from the `en` resources in
  `src/app/i18n/i18next.d.ts`.

### Multi-tenancy

Every person sees only their own rows, and this is enforced in the query, not
in a check afterwards:

- filter by `request.user` in the queryset itself;
- never accept a user id from the client;
- a row belonging to somebody else answers **404, not 403** — the id of a row
  they cannot see should tell them nothing;
- a `PublicationTarget` is reachable only through its publication's owner.

### Background work

- Tasks are idempotent and claim before they work: a conditional UPDATE whose
  rowcount decides, as in `social/sessions.py::claim` and
  `publishing/pipeline.py::claim`. `acks_late` gives at-least-once; the claim
  makes it effectively-once.
- Never retry what the platform decided about. A rejected file or an exhausted
  quota does not improve on repetition, and each attempt spends YouTube quota
  that cannot be recovered.
- Persist enough to resume: `PublicationTarget.resume_state` is why a killed
  worker continues rather than re-uploading gigabytes.

### SQLite

The web process and the worker write to the same file. That works because of
the PRAGMAs in `config/settings/base.py`, and because of two rules:

1. **Never hold a transaction open across a network call.** Read, close, call
   the platform, reopen, write.
2. **Throttle writes in loops.** The upload loop reports progress far more
   often than it should be written; the pipeline writes on whole percents.

There is no `SELECT ... FOR UPDATE SKIP LOCKED`. Use the conditional UPDATE.

Moving to PostgreSQL is prepared (`DATABASE_ENGINE`, portable ORM usage) and is
triggered by `database is locked` appearing in the worker log.

### API conventions

Every response carries a `status` string; the HTTP code follows from it
(`common/responses/contract.py::HTTP_STATUS`). Clients branch on the string, so a new
outcome is a new row there, not a new body shape.

```python
@require_post
@require_auth
@rate_limit("publications")
@validate(CreatePublicationSchema)
def publishing_create(request, data: CreatePublicationSchema): ...
```

`common/core/decorators.py::precondition` builds both sync and async wrappers
from one check, which is why this project does not need a framework layer here.

---

## Repository Structure

```text
backend/
├─ config/        settings/{base,dev,test}.py, urls, asgi, celery
├─ common/        one package per task: responses, access, rate_limit, request_body, encryption
├─ accounts/      User with its limits, sign-in
├─ social/        SocialAccount, OAuthSession, provider registry, connect/callback
├─ media/         MediaAsset, UploadSession, chunked upload, storage, sweeps
├─ publishing/    Publication, PublicationTarget, pipeline, tasks, API
└─ platforms/     plain package: oauth/, capabilities/, http/, youtube/

frontend/src/
├─ api/           RTK Query: baseApi + one module per area
├─ app/           store, router, providers, i18n
├─ domain/        pure types shared with the server's vocabulary
├─ features/      auth, composer, publications, accounts, settings, upload
├─ services/      files/, storage/, upload/chunkedUpload.ts
├─ components/    shared UI
└─ locales/       en, ru — one JSON per namespace
```

### File Placement Rules

- Anything touching a platform API, a token or a stored file is backend code.
- A new platform goes in `backend/platforms/<platform>/` and
  `publishing/publishers/<platform>.py`, plus one line each in
  `social/providers.py`, `publishing/views/platforms.py` and
  `publishing/publishers/__init__.py`.
- New screens go in `frontend/src/features/<feature>/`.
- Cross-feature reusable UI goes in `frontend/src/components/`.
- A new endpoint goes in `<app>/views/<name>.py`, one file per endpoint group.

---

## Environment Setup

### Required Tooling

- Node.js 24.x, npm
- Python 3.13
- Docker — only to run Redis

### Install and run

```bash
docker run -d --name anycast-redis -p 6379:6379 redis:alpine

cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Linux: .venv/bin/pip
cp .env.example .env                              # then fill it in
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py createsuperuser
.venv/Scripts/python -m uvicorn config.asgi:application --port 8000 --no-access-log
.venv/Scripts/python -m celery -A config worker --pool=solo -l info
.venv/Scripts/python -m celery -A config beat -l info

cd ../frontend
npm install
npm run dev                                        # http://localhost:5173
```

### Setup Notes

- `TOKEN_ENCRYPTION_KEYS` is **required**; the server refuses to start without
  it. Generate one with the command printed in that error.
- YouTube needs a Google Cloud OAuth client of type **Web application** with
  the YouTube Data API v3 enabled, and
  `http://localhost:5173/api/social/youtube/callback` as an authorised redirect
  URI.
- The Vite dev server is part of the OAuth path: the redirect lands on its
  port and is proxied to Django. It has to be running to connect an account.

---

## Development Commands

| Task | Command | Notes |
| --- | --- | --- |
| Backend tests | `.venv/Scripts/python manage.py test --settings=config.settings.test` | No network, no Redis, no disk |
| Migrations | `manage.py makemigrations` / `manage.py migrate` | |
| Backend server | `python -m uvicorn config.asgi:application --port 8000 --no-access-log` | Access log off on purpose: the OAuth callback URL carries a one-time code |
| Worker | `python -m celery -A config worker --pool=solo -l info` | `--pool=solo` because Windows has no fork |
| Beat | `python -m celery -A config beat -l info` | Separate process: `-B` is refused on Windows |
| Media sweep | `manage.py sweep_media` | What the periodic tasks do, on demand |
| Frontend dev | `npm run dev` | Proxies `/api` and `/admin` to Django |
| Frontend build | `npm run build` | Runs `tsc` then `vite build` |
| Typecheck | `npx tsc --noEmit` | |
| Lint | `npm run lint` | |
| Frontend tests | `npm test` | Vitest |
| Format | `npm run format` | Prettier |

---

## Testing

- **Backend tests are mandatory** for new behaviour. They are Django
  `TestCase`, written as Given / When / Then, with the platform mocked at
  `platforms.http.transport.requests.request` so the real chunking and retry run.
- What must have a test: anything about who can see what, anything about
  tokens, the upload offsets, and every way a platform can refuse.
- **Frontend tests cover pure functions only** — hashtag normalisation, the
  chunk arithmetic. A mistake in the offsets is silent until a checksum fails
  at the end of a four-gigabyte upload. Component tests are not worth their
  cost here.
- A contract test asserts the YouTube defaults in TypeScript and Python agree.
  If they drift, a person sees one thing and gets another.

---

## Code Style And Naming

- Formatter: Prettier (`frontend/.prettierrc.json`)
- Linter: ESLint (typescript-eslint + `eslint-plugin-react-hooks`)
- Type policy: strict (`strict`, `noUnusedLocals`, `noUnusedParameters`)
- Comments policy: no comments and no docstrings. Code documents itself: name
  things clearly, extract a function whose name states the intent, let types
  carry the shape, put the reason for a refusal in its error or log message.
  A *why* that the code cannot carry (a platform's constraint, a quota, an
  operational procedure such as key rotation) goes in the README or an ADR.
  Test names and their Given / When / Then steps are the one exception.
- Import policy: relative within a module, no path aliases
- Styling: Tailwind utilities in `className`; no CSS modules, no `style` props

### Style Do / Don't

Do:

- use names that reflect intent;
- keep each feature and platform folder cohesive and self-contained;
- follow the shape of the existing platform when adding another one;
- reach for an existing HeroUI component before building one by hand.

Don't:

- add comments or docstrings;
- put unrelated logic in a shared "utils" file;
- hardcode colours or add a second component library;
- call `fetch` from a component.

---

## Security And Safety Boundaries

Treat this section as mandatory.

### Hard Rules

- Never commit secrets, OAuth client secrets, tokens, or `.env`.
- Never hardcode credentials in source, tests, or docs.
- Platform tokens live only in `SocialAccount`, encrypted with
  `EncryptedTextField`. A token must never appear in an API response, a log
  line, a `__str__`, the admin, or the SPA.
- **No secret may go in a `VITE_*` variable.** The frontend bundle is public.
- Report the class of a network exception, never its text: a `requests`
  exception contains the URL, and the token request body carries
  `client_secret`. `urllib3` is pinned to WARNING for the same reason.
- `state` in an OAuth callback is checked twice: that we issued it and it is
  still pending, and that it belongs to the person whose session cookie is on
  the request.

### Human Approval Required Before

- changing OAuth or credential handling (`backend/social/`,
  `backend/platforms/*/oauth.py`, `backend/common/encryption/`);
- deleting user data or stored media;
- installing or replacing major dependencies;
- rotating secrets or changing how `.env` is read;
- anything that would publish the Django admin.

### Sensitive Areas

- Authentication: `backend/accounts/`, `backend/common/access/`, `backend/common/core/`
- Platform authorisation: `backend/social/`, `backend/platforms/*/oauth.py`
- Encryption: `backend/common/encryption/`
- Configuration: `backend/.env`

---

## Writing Code

Invoke the `caveman` skill before writing code. Keep narration around the
change ultra-compressed; the code itself still follows normal syntax and the
Code Style rule above.

## Tools

- For bash commands — @.claude/RTK.md

---

## Optional Cross-Tool Alignment

If this repository starts using other tool-specific AI instruction files
(`.github/copilot-instructions.md`, `.cursorrules`, `AGENTS.md`, …), keep them
aligned with this file. Prefer this file as the authoritative source and mirror
only the minimum into the others.

---

## Maintenance Checklist For Humans

- Update this file whenever the architecture, stack, commands, or workflow change.
- Keep commands executable exactly as written.
- Record decisions in `docs/adr/`, not here — this file says what is, the ADRs
  say why.
