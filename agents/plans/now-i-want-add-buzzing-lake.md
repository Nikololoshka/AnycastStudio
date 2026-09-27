# Instagram Reels publishing

## Context

Instagram was a desktop-client feature (tag `v0-desktop`), removed in the web
migration. Bring it back as the third server-side platform, following
`docs/platforms/adding-a-platform.md` and mirroring `platforms/tiktok/`.
Decisions below were settled in a grilling session.

## Decisions

| # | Decision |
| --- | --- |
| Login | Facebook Login (Page linked to an IG professional account), same Meta app as the old broker |
| Callback | Our own `/api/social/instagram/callback` via `PUBLIC_REDIRECT_ORIGIN` + ngrok; add that URI to the app's Valid OAuth Redirect URIs. Broker not used |
| Scopes | `instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement` |
| Token | code → user token → `fb_exchange_token` long-lived → **Page token** (never expires) stored as `access_token`; `token_expires_at=None`, no refresh token; `refresh()` raises → `needs_reauth` |
| Revoke | `DELETE /{fb_user_id}/permissions` with app token `app_id|app_secret`; `fb_user_id` in `SocialAccount.extra` |
| Account pick | first Page with `instagram_business_account`; fallback via `debug_token` `granular_scopes[].target_ids` when `me/accounts` empty; clear error if none |
| Media | Reels only (`media_type=REELS`, `upload_type=resumable`) |
| Scheduling | `deferredUpload` |
| Upload | container create → `rupload.facebook.com/ig-api-upload/<ver>/<container>` with `offset`/`file_size`, 4 MiB chunks; `ResumeState(container_id, offset, created_at)`; resume from offset (read from Meta if rupload exposes it — check docs), new container if offset rejected / >24h / EXPIRED |
| Publish | `publish` → `processing` with `container_id`, `confirming_since`, `polls`; `confirm` polls `status_code`: `FINISHED` → `media_publish` → `completed` (+ permalink best-effort), `ERROR`/`EXPIRED` → raise; deadline 30 min; no retry of `media_publish` refusals |
| Options | `shareToFeed` (default `true`), `coverFrameSeconds` (default `0`, ≥0, sent as `thumb_offset` ms) |
| Caption | like TikTok: `caption_of(title, description, hashtags)` |
| Validation | mp4/mov; size/duration from current Meta Reels docs; caption ≤ 2200, ≤ 30 hashtags; Graph version = one constant in `api.py`, current stable |
| Settings | `INSTAGRAM_CLIENT_ID`, `INSTAGRAM_CLIENT_SECRET` in `base.py`/`test.py`, `.env.example` block |

## Commits

### 1. Shared: revoke without refresh token
- `backend/social/services.py::disconnect` — call `provider.revoke` when an
  access token exists, not only when `refresh_token` is set. YouTube/TikTok
  unchanged; tests in `social/tests/`.
- Confirm `_refreshed_bundle` already marks `needs_reauth` on empty refresh
  token (pipeline 401 path) — test for it.
- Sensitive area (`backend/social/`) — approved in grilling.

### 2. Backend platform
`backend/platforms/instagram/` mirroring `platforms/tiktok/`:
`api.py` (`send`/`call` over `platforms.http`, Meta error envelope `{"error":{code,error_subcode,message}}` checked on 200, code in `PlatformFailure.details`), `oauth.py` (`InstagramProvider`, `uses_pkce=False`, `redirect_uri` via `oauth.callback_url`), `upload.py`, `status.py`, `video_options.py`, `capabilities.py`, `errors.py`.
`publishing/publishers/instagram.py`; one line each in `social/providers.py`, `publishing/views/platforms.py`, `publishing/publishers/__init__.py`.
Tests: `platforms/tests/test_instagram_*.py` (stateful double by URL: container params, every byte once/in order, resume, expired container → new, 401 → `NeedsFreshToken`, envelope error on 200, each status refusal), `publishing/tests/test_instagram.py` (local refusals no call, `processing` not `completed`, confirm completes/fails/times out, duplicate confirm no-op), `social/tests/test_instagram.py` (consent URL, callback incl. `debug_token` fallback, no IG account error, revoke with app token).

### 3. Frontend + docs
`frontend/src/platforms/instagram/`: `settings.ts` (`INSTAGRAM_DEFAULT_SETTINGS` flat literal), `InstagramDescriptor.ts`, `InstagramSettingsPanel.tsx` (`SettingSwitch`, `SettingNumber`), `settings.test.ts`.
Register in `domain/platform/order.ts::AVAILABLE_PLATFORMS`, `platforms/registry.ts`, `platforms/settings.ts`, `features/composer/PlatformTab.tsx`. Locales `en`+`ru` `platforms.json` (reuse `shareToFeed`, add `coverFrame`, any new `DraftError` codes + `composer.summary.invalid`).
Contract test in `publishing/tests/test_platforms.py::ContractScenarios`.
`docs/platforms/instagram.md`: app setup, redirect URI, limits, error mapping.

## Verification
- `.venv/Scripts/python manage.py test --settings=config.settings.test`
- `npx tsc --noEmit`, `npm run lint`, `npm test`
- Manual: restart worker+beat, ngrok + `PUBLIC_REDIRECT_ORIGIN`, connect IG, publish a short Reel now and one scheduled; watch `processing` → `completed`, kill worker mid-upload to check resume, disconnect → revoke.
