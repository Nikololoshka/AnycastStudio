# AnycastStudio

Publish one video to your platforms from a single composer. Upload it, write
the title once, press Publish — and close the tab. The server finishes the job.

> **Status.** The first web release covers **YouTube** and runs locally. X,
> Instagram and TikTok were written for the earlier desktop client and come
> back one at a time; they are preserved under the `v0-desktop` tag. Accounts
> are created by an administrator — there is no sign-up.

---

## How it works

```
Browser (Vite dev server, :5173)
  │  serves the SPA, proxies /api to Django — one origin, so the session
  │  cookie and CSRF work without CORS
  ▼
Django / uvicorn (:8000) ──► SQLite (WAL)
  │                       └─► Redis (cache, sessions, Celery broker)
  ▼
Celery worker ──► backend/media_files ──► YouTube Data API
```

The browser hands the video to the server in resumable chunks, then asks the
server to publish it. From that point nothing depends on the tab staying open:
a worker uploads the file, and if it dies partway it continues from the offset
YouTube confirmed rather than starting the file again.

Scheduling is handed to the platform. A video due later goes up private with a
`publishAt`, and YouTube publishes it — so nothing of ours has to be running at
that moment.

---

## Requirements

- Node.js 24
- Python 3.13
- Docker — only to run Redis

---

## Quick start

```bash
# 1. Redis
docker run -d --name anycast-redis -p 6379:6379 redis:alpine

# 2. Backend
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt          # Linux/macOS: .venv/bin/pip
cp .env.example .env                                   # fill it in — see below
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py createsuperuser

# 3. Two backend processes
.venv/Scripts/python -m uvicorn config.asgi:application --port 8000 --no-access-log
.venv/Scripts/python -m celery -A config worker -B --pool=solo -l info

# 4. Frontend
cd ../frontend
npm install
npm run dev
```

Open <http://localhost:5173> and sign in with the account you just created.

---

## Configuration

Everything secret lives in `backend/.env`. Nothing secret may go in a `VITE_*`
variable — the frontend bundle is public.

| Variable | Required | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | yes | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `TOKEN_ENCRYPTION_KEYS` | yes | Encrypts platform tokens at rest. The server refuses to start without it; the error prints the command that generates one. Comma-separated, newest first, so a key can be rotated without downtime. **Back it up separately from the database** — losing it means everyone reconnects every account. |
| `PUBLIC_ORIGIN` | yes | `http://localhost:5173`. OAuth redirect URIs are built from it. |
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | for YouTube | From Google Cloud, see below |
| `REDIS_URL` | no | Defaults to `redis://127.0.0.1:6379/0` |
| `SQLITE_PATH` | no | Defaults to `backend/db.sqlite3` |
| `MEDIA_ROOT` | no | Defaults to `backend/media_files` |
| `DJANGO_DEBUG` | no | On in development |

Per-person limits — file size, storage, uploads at once, publications per day —
are named constants in `config/settings/base.py` and become the defaults of a
new account's `Quota` row.

`frontend/.env.local` holds one optional value, `VITE_API_URL`, which is empty
for the same-origin setup above.

---

## Connecting YouTube

1. In the Google Cloud console, enable the **YouTube Data API v3**.
2. Create an OAuth client of type **Web application** — not Desktop.
3. Add `http://localhost:5173/api/social/youtube/callback` to the authorised
   redirect URIs.
4. Put the client id and secret in `backend/.env`.
5. Sign in to the app and connect the channel from **Accounts**.

The Vite dev server has to be running for this: the redirect lands on its port
and is proxied to Django.

**Quota.** The Data API allows roughly 10,000 units a day and a video upload
costs about 1,600 — six uploads a day, for the whole project rather than per
person. The app refuses past `MAX_PUBLICATIONS_PER_DAY` with a reason instead
of letting Google refuse without one, and a failed publication is never retried
automatically.

---

## Development

Layout, conventions and the rules that are easy to get wrong are in
[`CLAUDE.md`](CLAUDE.md). Decisions and their reasons are in
[`docs/adr/`](docs/adr/).

```bash
# backend
.venv/Scripts/python manage.py test --settings=config.settings.test

# frontend
npx tsc --noEmit
npm run lint
npm test
```

The backend tests need no network, no Redis and no real disk: the platform is
mocked at the HTTP layer, so the real chunking, offsets and retry policy run.

---

## Security

- Platform tokens are encrypted at rest and never leave the server — no API
  response, log line or admin page contains one.
- The session cookie is HttpOnly and same-origin; every mutation carries a CSRF
  token.
- An OAuth callback's `state` is checked both for being one we issued and for
  belonging to the person whose session is on the request.
- Uploaded video is deleted `MEDIA_RETENTION_HOURS` after everything using it
  finished, and an unused upload is swept sooner.
- The Django admin is never published. Reach it over an SSH tunnel.

---

## History

This started as a Windows desktop client built with Tauri, with four platform
integrations and the upload loops written in Rust. That version is tagged
`v0-desktop`; the Rust uploaders are the specification the Python ports follow,
and the three missing platforms are recovered from there.
