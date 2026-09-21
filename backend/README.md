# AnycastStudio backend

Django service that owns the platform accounts, the uploaded media and the
publishing pipeline. The browser talks only to this; it never calls a platform
API itself.

The migration from the Tauri desktop client is in progress. Today this app still
contains the original OAuth broker (Facebook/Instagram `start` / `callback` /
`poll`); it is replaced by a browser redirect flow in a later phase.

## Layout

- `config/settings/`: `base.py` holds everything shared, `dev.py` and `test.py`
  override what differs. Select one with `DJANGO_SETTINGS_MODULE`.
- `social/providers.py`: the provider abstraction (`build_auth_url`,
  `exchange_code`) and `FacebookProvider`. To add a platform, subclass
  `Provider` and register it in `PROVIDERS`.
- `social/views/`: one file per endpoint (`start.py`, `callback.py`, `poll.py`);
  `common.py` holds the shared response contract and the `guard()` decorator
  factory, which builds sync and async wrappers from one check.
- `social/sessions.py`: the `AuthSession` lifecycle. All database work is here.
  `claim()` is the conditional-UPDATE pattern every background task reuses —
  SQLite has no `SELECT ... FOR UPDATE SKIP LOCKED`.
- `social/models.py`: `AuthSession`. It stores only the SHA-256 of `poll_token`.
- `social/ratelimit.py`: per-IP rate limiting through the Django cache.

## Run

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Linux: .venv/bin/pip
.venv/Scripts/python manage.py test --settings=config.settings.test
.venv/Scripts/python manage.py migrate
.venv/Scripts/python -m uvicorn config.asgi:application --port 8000 --no-access-log
```

The tests mock the Graph API and need no network access.

## Notes

- SQLite runs with WAL, `busy_timeout` and `transaction_mode=IMMEDIATE` because
  the web process and the worker write to the same file. Never hold a
  transaction open across a network call.
- The uvicorn access log is off and log messages never include tokens, codes or
  the app secret: the OAuth callback URL carries a one-time `code`. `urllib3` is
  pinned to WARNING because its DEBUG output includes the token-exchange URL,
  which carries `client_secret`.
