# Regroup backend/common by task

## Context

`common/` is laid out by *kind* of code — `fields`, `guards` (decorators),
`schema`, `responses`, `tests` — so a file name says nothing about what it is
for (`schema.py` holds the request-body decorator). Regroup by *task*: one
package per task holding its decorator, its logic and its tests. Behaviour and
public names (`api_response`, `validate`, `require_auth`, `rate_limit`, …) stay
the same; only module paths move. Layout chosen by the user.

## Target layout

```text
backend/common/
├─ __init__.py
├─ guard.py                  guard()                          (from guards.py)
├─ responses/
│  ├─ __init__.py            exports api_response, HTTP_STATUS
│  ├─ contract.py            HTTP_STATUS, api_response        (from responses.py)
│  ├─ error_views.py         bad_request, permission_denied,
│  │                         csrf_failure, not_found, server_error
│  └─ tests.py               StatusScenarios, CsrfScenarios   (from tests.py)
├─ access/
│  ├─ __init__.py            exports require_method/_post/_get/_delete, require_auth
│  └─ decorators.py                                           (from guards.py)
├─ rate_limit/
│  ├─ __init__.py            exports rate_limit
│  ├─ decorators.py          rate_limit                       (from guards.py)
│  └─ counter.py             client_ip, is_rate_limited       (from ratelimit.py)
├─ request_body/
│  ├─ __init__.py            exports validate
│  ├─ decorators.py          validate                         (from schema.py)
│  └─ tests.py               MalformedBodyScenarios           (from tests.py)
└─ encryption/
   ├─ __init__.py            exports EncryptedTextField, current_key_version,
   │                         reset_cipher_cache
   ├─ fields.py              EncryptedTextField               (from fields.py)
   └─ keys.py                _key_without_version, _cipher,
                             current_key_version, reset_cipher_cache
```

- `tests.py` only where tests exist. The rate-limit and encryption scenarios
  stay in `accounts/tests.py` and `social/tests/test_accounts.py`: they test
  through real endpoints.
- Django's runner picks up `tests.py` (pattern `test*.py`); each package has
  `__init__.py`, so discovery works without `common` in `INSTALLED_APPS`.
- `git mv` where a file maps 1:1 (`schema.py` → `request_body/decorators.py`,
  `ratelimit.py` → `rate_limit/counter.py`, `fields.py` → `encryption/fields.py`,
  `responses.py` → `responses/contract.py`) so history follows.
- No comments, no docstrings (Code Style).

## Call-site updates

- Views import from the packages:
  `from common.access import require_auth, require_post`,
  `from common.rate_limit import rate_limit`,
  `from common.request_body import validate`,
  `from common.responses import api_response` —
  `accounts/views/auth.py`, `media/views/{assets,uploads}.py`,
  `publishing/views/{platforms,publications}.py`,
  `social/views/{accounts,connect}.py`.
- Dotted strings → `common.responses.error_views.*`: handlers in
  `config/urls.py`, `CSRF_FAILURE_VIEW` in `config/settings/base.py`.
- Encryption: `social/models.py`, `social/services.py`,
  `social/tests/test_accounts.py` (`from common.encryption import keys` for
  `reset_cipher_cache` / settings patch; `assertLogs("common.encryption.fields")`).
- Migration `social/migrations/0002_…py`: `common.fields.EncryptedTextField` →
  `common.encryption.fields.EncryptedTextField` (the path `deconstruct()` will
  emit). Import only; `makemigrations --check` must stay clean.
- Docs: `CLAUDE.md` (stack table, API conventions, repository tree,
  approval list, sensitive areas), `backend/README.md`, `docs/architecture.md`.

**Sensitive area:** encryption code is moved and split, not changed. Approving
this plan is the approval.

## Verification

```bash
cd backend
.venv/Scripts/python manage.py test --settings=config.settings.test   # 148 tests, OK
.venv/Scripts/python manage.py check
.venv/Scripts/python manage.py makemigrations --check --dry-run      # No changes detected
grep -rnE "common[./](fields|guards|ratelimit|schema)\b|common\.responses\.(not_found|server_error|bad_request)" \
  --include=*.py --include=*.md ..                                   # nothing left
```

Commit: two commits — first the earlier `common` review fixes, then the move.
