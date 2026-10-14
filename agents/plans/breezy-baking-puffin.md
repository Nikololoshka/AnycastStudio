# Backend in docker compose

## Context
Running the app for manual testing takes Redis in Docker plus three backend
terminals (uvicorn, celery worker, celery beat) and vite. Goal: `docker compose
up` brings up the whole server; the frontend stays `npm run dev` by hand.
First-time `.env` stays manual (user's choice).

## Files

### `backend/Dockerfile` (new)
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```
Source is not copied: it's bind-mounted, so a code change needs only
`docker compose restart`, not a rebuild. Rebuild only when `requirements.txt` changes.

### `backend/.dockerignore` (new)
`.venv`, `media_files`, `*.sqlite3*`, `__pycache__`, `.env` — keeps the build context tiny and secrets out of the image.

### `compose.yaml` (new, repo root)
```yaml
x-backend: &backend
  build: ./backend
  volumes: [./backend:/app, data:/data]
  environment:
    REDIS_URL: redis://redis:6379/0
    CELERY_BROKER_URL: redis://redis:6379/0
    SQLITE_PATH: /data/db.sqlite3
    MEDIA_ROOT: /data/media
  depends_on: [redis]

services:
  redis:
    image: redis:alpine
  api:
    <<: *backend
    command: sh -c "python manage.py migrate && uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --no-access-log"
    ports: ["127.0.0.1:8000:8000"]
  worker:
    <<: *backend
    command: celery -A config worker --pool=solo -l info
  beat:
    <<: *backend
    command: celery -A config beat -l info -s /data/celerybeat-schedule

volumes:
  data:
```
Decisions:
- `.env` is read exactly as today: `load_dotenv` picks up `/app/.env` from the bind mount; compose only overrides the four container-specific values (real env wins over `.env`, `override=False`). No `env_file`.
- Port bound to `127.0.0.1` only — admin isn't exposed on the LAN. Vite's proxy to `127.0.0.1:8000` works unchanged.
- SQLite + media live in a named volume `data`, not the host's `backend/db.sqlite3`: three containers sharing a WAL database over a Windows bind mount is unreliable (the `-shm` mmap). Consequence: a fresh DB — create the user once with `docker compose exec api python manage.py createsuperuser`.
- Redis has no published port and no volume: it's cache/sessions/broker; losing it on `down` just logs everyone out.

### `README.md`
Quick start: new top path — "Docker: `docker compose up --build`, then `docker compose exec api python manage.py createsuperuser`, then `cd frontend && npm install && npm run dev`". Current manual steps stay as "Without Docker".

### `CLAUDE.md`
One line: "Run the server: `docker compose up` from the repo root; frontend `npm run dev`."

## Verification
- `docker compose up --build`: api migrates and listens, worker shows `ready`, beat sends `dispatch-due-targets` every minute.
- `docker compose exec api python manage.py createsuperuser`, `npm run dev`, log in at http://localhost:5173; /admin renders styled.
- Upload a video and publish → task appears in worker logs; file lands in the `data` volume.
- Edit a view, `docker compose restart api` → change live.
- `docker compose down` + `up` → user and media survive (named volume).
- Backend tests unchanged: `.venv/Scripts/python manage.py test --settings=config.settings.test`.
