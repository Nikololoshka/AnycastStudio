# AnycastStudio

Publishes one video to YouTube, TikTok, Instagram and X from a single editor.
Django + Celery server, React SPA. Runs locally for a few users: accounts are
created in Django admin, no sign-up, no email, no deployment yet.

Stack: Python 3.13, Django 6.1 (plain views, no DRF), pydantic 2, Celery 5.6 on
Redis, aiohttp, SQLite (WAL); TypeScript 6.0, React 19.1, Redux Toolkit 2.12 /
RTK Query, react-router 8, HeroUI 3, Tailwind 4.3, i18next, Vite 8.

Domain rules: `.claude/rules/`. Why things are the way they are: `docs/adr/`.

## Verify a change

- Backend, from `backend/`:
  `.venv/Scripts/python manage.py test --settings=config.settings.test`
  (`.venv/bin/` on Linux). Model changed → `.venv/Scripts/python manage.py makemigrations`.
- Frontend, from `frontend/`: `npx tsc --noEmit`, `npm run lint`, `npm test`.
- Changed defaults in `frontend/src/platforms/*/settings.ts` → change the Python
  side too; `publishing/tests/test_platforms.py` fails on mismatch.

## Rules

- No comments or docstrings, including `ponytail:` markers: names and types
  carry intent, reasons go into error and log messages. Test names and
  Given / When / Then steps are the exception.
- No shared `utils` files: feature and platform folders are self-contained.
- Relative imports inside a module, no path aliases.
- Don't add a dependency when an installed one does the job.
- Publishing logic, tokens and platform API calls stay on the server, never in
  the SPA.

## Security

- Never commit secrets, OAuth client secrets, tokens or `.env`; never hardcode
  credentials in code, tests or docs.
- No secrets in `VITE_*` variables: the bundle is public.
- Platform tokens never reach an API response, log line, `__str__`, admin or
  the SPA.
- Run uvicorn with `--no-access-log`: the OAuth callback URL carries a one-time
  code.

Ask the human before you:

- change OAuth or credential handling (see `backend-social` rule);
- delete user data or stored media;
- add or replace a major dependency;
- rotate secrets or change how `.env` is read;
- do anything that exposes Django admin publicly.
