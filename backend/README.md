# `OAuth broker for the desktop app

A Django service that runs the OAuth sign-in on behalf of the desktop app and returns only the access token to it. 

API reference for clients: [docs/API.md](docs/API.md).

## Layout

- `multiposter/providers.py`: the provider abstraction (`build_auth_url`, `exchange_code`) and `FacebookProvider`. To add YouTube, TikTok or X, subclass `Provider` and register it in `PROVIDERS`. Each provider gets its own endpoints in `multiposter/urls.py` (`/multiposter/auth_<provider>/start`, `/callback`, `/poll`); the model and the views are shared.
- `multiposter/views/`: one file per endpoint: `start.py`, `callback.py`, `poll.py` (async long-poll); `common.py` has shared helpers.
- `multiposter/sessions.py`: the `AuthSession` lifecycle (create, claim, complete/fail, check for `/poll`). All database work is here.
- `multiposter/models.py`: `AuthSession`. It stores only the SHA-256 of `poll_token`.
- `multiposter/ratelimit.py`: per-IP rate limiting of `/start` and `/poll` through the Django cache.
- `Dockerfile`, `docker-compose.yml`: the container (uvicorn, SQLite on the `multiposter-data` volume).
- `deploy/nginx.conf`: the site config for nginx on the host (TLS, proxy to the container).

## Local run

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Linux: .venv/bin/pip
python manage.py test --settings=config.settings_test
DJANGO_DEBUG=1 python manage.py migrate
DJANGO_DEBUG=1 uvicorn config.asgi:application --port 8000 --no-access-log
```

The tests mock the Graph API and need no network access.

## Deploy (VPS, Docker + host nginx)

1. Copy the project to the server and create `.env` from `.env.example` (`FB_APP_SECRET` belongs only there). Set `PUBLIC_HOST` to your domain (e.g. `auth.example.com`). Set `CLIENT_TOKENS` to the token(s) the desktop app sends to `/start` (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`); comma-separate several to rotate without downtime. The server refuses to start without it unless `DJANGO_DEBUG` is on.
2. Build and start the container: `docker compose up -d --build`. Migrations run on every start. The app listens on `127.0.0.1:8000` only.
3. Copy `deploy/nginx.conf` to `/etc/nginx/sites-available/multiposter`, replace `auth.example.com`, and enable it:
   `ln -s /etc/nginx/sites-available/multiposter /etc/nginx/sites-enabled/`.
4. Get a certificate: `certbot --nginx -d auth.example.com` (or point `ssl_certificate` at an existing one), then `nginx -t && systemctl reload nginx`.
5. In the Facebook app settings, add `https://<PUBLIC_HOST>/multiposter/auth_facebook/callback` to **Valid OAuth Redirect URIs**.

Update: `git pull && docker compose up -d --build`. Logs: `docker compose logs -f`.

Notes:

- The nginx access log uses a format without the query string, and the uvicorn access log is off, because the callback URL contains the one-time `code`.
- The container runs one uvicorn process with SQLite, which is enough here. For several workers, use PostgreSQL (`DATABASE_ENGINE=postgresql`, add `psycopg[binary]` to `requirements.txt`) and a shared cache for the rate limit, or rate-limit in nginx (`limit_req`).
- `/poll` holds the connection for up to 25 s; nginx `proxy_read_timeout` is 60 s, and clients need an HTTP timeout above 25 s.
