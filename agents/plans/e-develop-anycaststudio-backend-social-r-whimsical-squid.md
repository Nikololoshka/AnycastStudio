# Clean up social/views/accounts.py

## Context
`social_accounts` / `social_account` say which URL they serve, not what they
do (list connected accounts / disconnect one). The file also carries two
one-use helpers (`_connected_accounts_of`, `_disconnect`). The user wants
telling names, no one-use helpers of a couple of lines, and the repositories
reused where they fit.

## Changes

### 1. Rename the views (keep the app prefix used by every view, as `publishing_*`)
- `social_accounts` → `social_list_connected_accounts`
- `social_account` → `social_disconnect_account`
- Update `social/views/__init__.py` and `social/urls.py`. URL paths and URL
  names stay; tests use paths only.

### 2. Inline `_connected_accounts_of`
One use, one line:
`SocialAccount.objects.filter(user=request.user).exclude(status=SocialAccount.Status.REVOKED).order_by("platform", "display_name")`.
`DjangoAccountRepository.get_connected_accounts` is **not** reused here: it
returns `AccountRecord(id, platform, status)`, while the list needs
`display_name`, `avatar_url`, `external_id`, `connected_at` for
`serializers.account_json`. Widening the domain record for one read-only
view would bloat a value the publication checks use.

### 3. Remove `_disconnect` — the ownership check moves into the use case
`AccountService.disconnect(account_id)` → `disconnect(owner_id, account_id)`
(`services/usecases/accounts/account_service.py`), which first calls the
existing `self._accounts.get_connected_account(owner_id, account_id)`
(raises `NotFound` → 404 for someone else's or an already disconnected
account), then does what it does today. The view becomes:
```python
container().run(lambda services: services.account_service.disconnect(owner_id, pk))
```
This reuses the repository instead of reaching `container().accounts` from
the view.

## Files
- `backend/social/views/accounts.py`, `backend/social/views/__init__.py`, `backend/social/urls.py`
- `backend/services/usecases/accounts/account_service.py`
- `backend/services/tests/test_account_scenarios.py` — `disconnect(7)` calls get the owner id
- Sensitive area (`services/usecases/accounts/`): approved via this plan.

## Verification
- `.venv/Scripts/python manage.py test --settings=config.settings.test` — 506 OK.
  `social/tests/test_accounts.py::test_another_persons_account_is_not_found`
  and `test_a_disconnected_account_is_no_longer_listed` cover the 404 and the list.
- `grep -rn "social_accounts\b\|views.social_account\b"` leaves only the `related_name`.
- No commit unless asked.
