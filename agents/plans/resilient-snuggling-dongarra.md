# Plan: publish video to X

## Context
Add X (x.com) video posting beside YouTube, TikTok and Instagram, following
`docs/platforms/adding-a-platform.md`. The desktop code in `v0-desktop` is only
a reference: it had a public client secret, never checked `state`, used the
retired `?command=` upload, skipped resume and never polled processing.

## Decisions (from grilling)
| Topic | Decision |
| --- | --- |
| API access | Pay-per-use credits. Don't retry what X decided about; `POST /2/tweets` is sent once (`attempts=1`) |
| Limits | Kept from desktop: 512 MiB, 0.5–140 s, mp4/mov, `media_category=tweet_video` |
| Text | `caption_of(title, description, hashtags)` as Instagram/TikTok do; `title=true` |
| Counting | Plain length ≤ 280. Server uses UTF-16 length so it matches JS `.length` (reuse the `utf16_length` idea from `platforms/tiktok/video_options.py:78`, own copy in `platforms/x`) |
| Scheduling | `deferredUpload`, so no shared change |
| Processing | `publish` → `processing`; `confirm` polls STATUS, then creates the post |
| Settings | All four from desktop: `replyAudience`, `madeWithAi`, `paidPartnership`, `superFollowersOnly`; only non-default fields are sent |
| Resume | `ResumeState(media_id, next_segment, created_at)`; resume while under 23 h, re-INIT after |
| Lost reply on post | `posting_started` marker in `resume_state` before the call; if confirm finds the marker without a post id, fail with "may have been posted — check X", never re-post |

**Needs your approval (OAuth, a sensitive area):** a new confidential-client
provider with HTTP Basic client auth, which no other provider uses. `revoke`
revokes the refresh token and then the access token, best-effort.

## Facts (docs.x.com, 2026-09-27)
- OAuth: authorize at `https://x.com/i/oauth2/authorize`, token at
  `POST https://api.x.com/2/oauth2/token`, revoke at `/2/oauth2/revoke`, S256
  PKCE, `Authorization: Basic base64(id:secret)`. Scopes: `tweet.read
  tweet.write users.read media.write offline.access`. Access token lasts 2 h;
  the refresh token is single-use, and the existing refresh lease covers that.
- Identity: `GET /2/users/me?user.fields=profile_image_url`, giving
  `external_id=id`, `display_name=username`, avatar.
- Upload: `POST /2/media/upload/initialize` (`media_type`, `total_bytes`,
  `media_category`), then `POST /2/media/upload/{id}/append` (multipart
  `segment_index`, `media`, ≤ 5 MB → use 4 MiB, not the 8 MiB
  `PLATFORM_CHUNK_BYTES`), then `POST /2/media/upload/{id}/finalize`. STATUS:
  `GET /2/media/upload?command=STATUS&media_id=` → `processing_info.state`
  (pending / in_progress / succeeded / failed, with `error`). The media id
  expires after 24 h.
- Post: `POST /2/tweets` `{text, media:{media_ids:[id]}, reply_settings?,
  made_with_ai?, paid_partnership?, for_super_followers_only?}` → 201
  `data.id`. URL: `https://x.com/i/web/status/<id>`.
- Errors: `{title, detail, type: ".../problems/<kind>", status}` or `errors[]`.
  Keep `<kind>` in `PlatformFailure.details`.

## Commits (tests with each; each one reviewed before the next)
No shared change is needed: Basic auth is passed as `headers` through
`platforms.http.request`, and deferred scheduling, confirm polling and the
refresh lease already exist.

### 1. Backend: `backend/platforms/x/` + publisher + registrations
Mirror `platforms/instagram/`:
- `api.py`: `API_ROOT="https://api.x.com/2"`, `_attempt`/`send` over
  `platforms.http` (`with_retry`), `failure_of(response)` reading the problem
  `type` into `details`, `call(method, path, token, *, attempts=None, **kw)`
  with a Bearer token. A 401 raises `AUTHENTICATION`. Duplicate content (403)
  and `usage-capped` stay non-retryable.
- `oauth.py`: `XProvider` (`name="x"`, `uses_pkce=True`, `s256_challenge`,
  `callback_url("x")`, Basic header, `OAUTH_ATTEMPTS`, `ProviderError` on
  failure, `"X_CLIENT_ID is not configured"`).
- `upload.py`: `ResumeState` (`as_dict`, `of`, `expired`), INIT once, APPEND
  per segment with `should_cancel` checked before each one, and a
  `NeedsFreshToken(state)` on 401. FINALIZE returns the media id.
- `status.py`: `fetch(token, media_id) -> ProcessingStatus` (`is_ready`,
  `is_failed`), `failure_of(status)`, `create_post(token, text, media_id,
  options) -> post_id` (`attempts=1`), `post_url(id)`.
- `video_options.py`: `VideoOptions(reply_audience, made_with_ai,
  paid_partnership, super_followers_only)`, a lenient `video_options_of`,
  camelCase `as_json`, `caption_of`, `utf16_length`, and
  `reply_settings_of` (`everyone` → omitted).
- `capabilities.py`: `capabilities()` (label "X", `deferredUpload`,
  title/description/hashtags true, drafts false, 512 MiB, mp4/quicktime) and
  `validate(caption, size_bytes, mime_type, duration_seconds)` returning the
  codes `captionTooLong`, `fileTooLarge`, `unsupportedType`, `videoTooShort`,
  `videoTooLong`.
- `errors.py`, `__init__.py` re-exports as in Instagram.
- `publishing/publishers/x.py`, the same shape as
  `publishing/publishers/instagram.py`. `confirm`: when `posting_started` is
  set, fail. Otherwise, while STATUS isn't ready return `None`; if it failed,
  raise; once it's ready, write the marker (a conditional update on
  `resume_state`), post, and return `COMPLETED` with the URL.
- Registrations: `publishing/publishers/__init__.py`, `social/providers.py`,
  `publishing/views/platforms.py`, `config/settings/base.py` +
  `test.py` (`X_CLIENT_ID/SECRET`), and an `.env.example` block (a
  confidential client of type "Web App", the redirect
  `http://localhost:5173/api/social/x/callback`).
- Tests, with a stateful double routed by URL at
  `platforms.http.transport.requests.request`:
  - `platforms/tests/test_x_upload.py`: the INIT body, every byte once and in
    order, 4 MiB segments, resume inside and after 23 h, 401 →
    `NeedsFreshToken`, cancel.
  - `test_x_status.py`: state mapping, failed processing, the error envelope.
  - `test_x_oauth.py`: the consent URL, the Basic header, and that the secret
    never appears in any log.
  - `social/tests/test_x.py`: a full callback.
  - `publishing/tests/test_x.py`: local refusals make no call; upload →
    `processing`; confirm waits / completes / fails / times out; a
    `posting_started` marker without a reply means failure and no second
    post; a duplicate confirm does nothing.

### 2. Frontend + docs
- `frontend/src/platforms/x/`:
  - `settings.ts`: `XSettings`, a flat `X_DEFAULT_SETTINGS` literal,
    `xSettingsOf`, `xCaptionOf`, the limits.
  - `XDescriptor.ts`: `validate(draft)` with the same codes.
  - `XSettingsPanel.tsx`: `SettingSelect` for reply audience, three
    `SettingSwitch`.
  - `settings.test.ts`: pure functions only.
  - `index.ts`.
- Registrations: `domain/platform/order.ts` (`AVAILABLE_PLATFORMS`),
  `platforms/registry.ts`, `platforms/settings.ts`,
  `features/composer/PlatformTab.tsx`. The glyph, brand colour and `x`
  locale blocks already exist; check that `ru` matches `en`.
- Contract test: an X case in
  `publishing/tests/test_platforms.py::ContractScenarios`.
- Docs: `docs/platforms/x.md` (decisions above, app setup). Update the X
  notes in `adding-a-platform.md` (endpoints changed) and the CLAUDE.md scope
  line ("YouTube, TikTok, Instagram and X").

## Verification
- `.venv/Scripts/python manage.py test --settings=config.settings.test`
- `npx tsc --noEmit`, `npm run lint`, `npm test`
- Manual: create an X app (pay-per-use, OAuth 2 confidential) with the
  localhost redirect. If X rejects localhost, use `PUBLIC_REDIRECT_ORIGIN` +
  ngrok as in `docs/platforms/tiktok.md`. Restart the worker and beat, connect
  the account, and publish a short mp4 now and one scheduled. Watch the
  target go uploading → processing → completed with a working link.
