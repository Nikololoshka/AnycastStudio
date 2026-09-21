# Instagram Reels Publishing — Implementation Plan

## Context

YouTube and TikTok publishing are already implemented. Instagram is currently a stub
(`InstagramAdapter`/`InstagramSettingsPanel` throw `not implemented`, `auths.instagram`
rejects everything). This plan fleshes out Instagram Reels publishing to the same
standard, following the exact adapter/auth/upload-command pattern already established
by YouTube and TikTok, while accounting for the two ways Instagram's Graph API genuinely
differs from Google/TikTok's OAuth and upload protocols:

- Meta's OAuth redirect_uri validation is **exact-match**, not wildcard-port like
  Google's installed-app flow the shared loopback server currently assumes — so
  Instagram needs a **fixed local port** instead of the existing dynamic one.
- Instagram Login access tokens are **long-lived (~60 days), refreshed via a GET
  endpoint that takes the current token itself** — not a `refresh_token` grant like
  YouTube/TikTok — so `getValidAccessToken` needs different refresh logic.
- There's no server to host video at a public URL, so Reels publishing uses Meta's
  **resumable binary upload** (`upload_type=resumable` container + direct POST of
  bytes to a `rupload.facebook.com` session), implemented as a Rust upload-loop
  command per the architecture's narrow exception — not the `video_url`-fetch method.

Decisions already made with the user (do not re-litigate): Instagram Login (not
Facebook Login/Pages), self-created Meta app, self-use only (no App Review), resumable
upload in Rust, a `shareToFeed` toggle in the settings panel, and a **fixed OAuth
callback port (42813)** registered as `http://localhost:42813/callback` in the Meta
dashboard.

## API surface being targeted (Meta Graph API / Instagram Login / Content Publishing)

Exact endpoint paths/field names should be re-checked against Meta's current Graph API
docs at implementation time (they evolve across `vXX.0` versions) — treat this as the
best-known concrete shape to implement against, not a guarantee.

| Step | Call |
|---|---|
| Authorize | `GET https://www.instagram.com/oauth/authorize` — `client_id`, `redirect_uri`, `response_type=code`, `scope=instagram_business_basic,instagram_business_content_publish`, `state`. No PKCE. |
| Token exchange (short-lived) | `POST https://api.instagram.com/oauth/access_token` (form) — `client_id`, `client_secret`, `grant_type=authorization_code`, `redirect_uri`, `code` → `{access_token, user_id}` (~1h). |
| Long-lived exchange | `GET https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=...&access_token=...` → `{access_token, token_type, expires_in}` (~60 days). |
| Refresh | `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=...` → `{access_token, expires_in}`. Token must be ≥24h old to refresh. |
| Own account | `GET https://graph.instagram.com/v21.0/me?fields=id,username,profile_picture_url&access_token=...` |
| Create container (resumable) | `POST https://graph.instagram.com/v21.0/{ig-user-id}/media` — `media_type=REELS`, `upload_type=resumable`, `caption`, `share_to_feed`, `access_token` → `{id: containerId, ...}` (upload target derived from container id if no separate URL is returned — confirm empirically). |
| Binary upload | `POST https://rupload.facebook.com/ig-api/v21.0/{containerId}` — headers `Authorization: OAuth {token}`, `offset`, `file_size`, `Content-Type: {mime}`, body = raw chunk bytes. POST-based (not PUT like YouTube). |
| Container status | `GET https://graph.instagram.com/v21.0/{containerId}?fields=status_code,status&access_token=...` → `IN_PROGRESS`/`FINISHED`/`ERROR`/`EXPIRED`. |
| Publish | `POST https://graph.instagram.com/v21.0/{ig-user-id}/media_publish` — `creation_id={containerId}`, `access_token` → `{id: mediaId}`. |
| Permalink (best-effort) | `GET https://graph.instagram.com/v21.0/{mediaId}?fields=permalink&access_token=...` |

## Implementation

### 1. Fixed-port OAuth loopback

- `src-tauri/src/commands/oauth.rs`: add `start_fixed_port_oauth_callback_server(port: u16, state: State<OAuthCallbackState>) -> Result<u16, String>` — same body as `start_oauth_callback_server` but binds `tiny_http::Server::http(format!("127.0.0.1:{port}"))` instead of `127.0.0.1:0`. Reuses `await_oauth_callback`/`OAuthCallbackState` unchanged. Leave `start_oauth_callback_server` untouched (YouTube/TikTok/X keep the dynamic port).
- `src-tauri/src/lib.rs`: register the new command in `generate_handler!`.
- `src/services/auth/oauthLoopback.ts`: add `startFixedPortOAuthCallbackServer(port: number): Promise<number>` wrapping `invoke('start_fixed_port_oauth_callback_server', { port })`.
- Fixed port: **42813**. Register `http://localhost:42813/callback` as the exact Valid OAuth Redirect URI in the Meta App Dashboard (Instagram Login product). Keep host (`localhost`) consistent between the dashboard entry and the TS-built `redirectUri`.

### 2. Env vars

- `.env.local` (user-managed): `VITE_INSTAGRAM_CLIENT_ID`, `VITE_INSTAGRAM_CLIENT_SECRET`.
- `src/vite-env.d.ts`: add both to `ImportMetaEnv`, matching the YouTube/TikTok entries already there.

### 3. `src/platforms/instagram/InstagramAuth.ts` (new)

Model on `YouTubeAuth.ts`/`TikTokAuth.ts`, implementing `PlatformAuth`
(`connect/disconnect/getAccount/getValidAccessToken`):

- `StoredCredential { accessToken, obtainedAt, expiresAt }` — no `refreshToken` field
  (Instagram Login refreshes using the current access token itself, not a refresh
  token).
- `connect()`: `startFixedPortOAuthCallbackServer(42813)` → build `redirectUri` →
  build authorize URL (no PKCE) → `openUrl` → `awaitOAuthCallback()` → exchange code
  for short-lived token → exchange for long-lived token → `fetchOwnUser` → build
  `ConnectedAccount` (`id: 'instagram:' + user.id`) → `storeCredential`.
- `disconnect(accountId)`: no known Instagram Login revoke endpoint — just
  `deleteCredential(accountId)`; note in a comment-free way (or PR description) that
  the user may need to revoke access manually via Instagram's own connected-apps
  settings.
- `getAccount()`: throw, same pattern as the other two auths.
- `getValidAccessToken(accountId)`: if remaining life is healthy, return the stored
  token as-is. If remaining life drops below a safety threshold (e.g. 5 days) **and**
  the token is ≥24h old, call `refreshLongLivedToken`, persist the refreshed
  credential (reset `obtainedAt`), return the new token. If refresh is due but the
  token isn't 24h old yet, just return the still-valid current token. If the token is
  already fully expired, throw — the user must `connect()` again (no recovery path,
  unlike YouTube/TikTok's refresh-token grant).

### 4. `src-tauri/src/commands/instagram_upload.rs` (new)

Model on `tiktok_upload.rs` for cancellation state/retry/backoff (`with_retry`,
`classify`, `jitter_ms`, `MAX_ATTEMPTS=5`, `UploadError` tagged enum
`network`/`authentication`/`platform`/`unknown`), and on `youtube_upload.rs`'s
offset-driven loop for the upload phase (since Meta's rupload protocol is
offset/file_size-header-driven rather than TikTok's pre-computed chunk-count
protocol):

- `InstagramUploadCancellations` state, `UploadVideoParams { upload_id, path,
  mime_type, access_token, ig_user_id, metadata: { caption, share_to_feed } }`,
  `UploadOutcome { container_id }`, `UploadProgressEvent` — same field shapes as the
  sibling commands.
- `create_container(...)`: `POST {base}/{ig_user_id}/media` with `media_type=REELS`,
  `upload_type=resumable`, `caption`, `share_to_feed`, `access_token` → parse
  container id from response. **Flag for empirical verification**: whether the
  response includes a separate upload-session URL or whether the rupload URL is just
  `rupload.facebook.com/ig-api/v21.0/{container_id}`.
- `put_chunk(...)`: `POST` (not PUT) to the rupload URL with `Authorization: OAuth
  {token}`, `offset`, `file_size`, `Content-Type: {mime}` headers, chunk bytes as
  body; wrapped in `with_retry`.
- `run_upload(...)`: `while offset < total_size` loop sending chunks, checking the
  cancellation flag each iteration, emitting progress via the `Channel` after each
  chunk; on completion return `UploadOutcome { container_id }`.
- No cross-call resume state (no `sessionUri`/`resumeOffset` in `UploadError`) — on
  any failure the whole upload retries from scratch with a new container, matching
  TikTok's simpler (non-resumable-across-calls) contract rather than YouTube's.
- Register in `src-tauri/src/commands/mod.rs` (`pub mod instagram_upload;`) and
  `src-tauri/src/lib.rs` (`.manage(...)` + both commands in `generate_handler!`). No
  new Cargo dependency.

### 5. `src/platforms/instagram/instagramUploadCommand.ts` (new)

Model on `tiktokUploadCommand.ts`:

- `uploadVideoToInstagram(uploadId, path, mimeType, getAccessToken, metadata, onProgress)`
  → invokes `upload_video_instagram` via a `Channel`, retries once on an
  `authentication`-typed error after refreshing the token (same pattern as TikTok's
  adapter-level retry), then polls container status (`pollContainerStatus`, same
  backoff constants as TikTok's `pollPublishStatus`: `[10s,30s,60s,120s]` over a
  5-minute deadline) before returning `{ containerId }`.
- `cancelInstagramUpload(uploadId)` → `invoke('cancel_instagram_upload', { uploadId })`.

### 6. `src/platforms/instagram/InstagramAdapter.ts` (implement stub)

Model on `TikTokAdapter.ts`:

- Keep `getCapabilities()` as already stubbed (`scheduling:'local'`, `title:false`,
  `description:true`, `hashtags:true`, `drafts:false`, 1GB max, mp4/mov).
- `validate()`: file size + mime type checks against capabilities, same shape as
  TikTok's — no invented duration check unless `VideoFile` already exposes duration
  (check `src/domain/video/types.ts`; skip if absent).
- `mediaMetadataOf(publication)`: `caption` = description + `#hashtag` list appended;
  `shareToFeed = Boolean(publication.settings.shareToFeed ?? true)`; `igUserId =
  publication.accountId.split(':')[1]`.
- `upload()`: try/catch around `uploadVideoToInstagram(...)`, return `{success:true,
  videoId: result.containerId}` or `{success:false, error: toPublicationError(error)}`.
- `publish()`: guard on missing `uploadedVideoId` (like YouTube's), `POST
  .../media_publish` with `creation_id`, on failure return a `platform` error; on
  success best-effort fetch the permalink for `publishedUrl` (swallow failure).
- **No `schedule()`** — matches TikTok; `scheduling:'local'` already tells
  `UploadManager` to call `publish()` directly.

### 7. `src/platforms/instagram/InstagramSettingsPanel.tsx` (implement stub)

Model on `TikTokSettingsPanel.tsx`: one `Switch` bound to
`state.composer.platformSettings.instagram.shareToFeed` (default `true`), dispatching
`setPlatformSettings({platform:'instagram', settings:{shareToFeed: checked}})`.

### 8. Wiring

- `src/platforms/instagram/index.ts`: export `InstagramAuth` alongside the existing
  exports.
- `src/platforms/auth.ts`: replace `instagram: notImplemented('instagram')` with
  `instagram: new InstagramAuth()`.
- No changes needed to `capabilities.ts` or `composerSlice.ts` (already wired for
  Instagram).

## Verification

1. **Typecheck**: `npx tsc --noEmit`. **Rust**: `cargo check` inside `src-tauri` (confirms
   `instagram_upload.rs` compiles and is registered correctly).
2. **Lint**: `npm run lint`.
3. **OAuth smoke test**: `npm run tauri dev`, connect an Instagram Business/Creator
   account that has a role on the Meta app. Confirm the browser opens the authorize
   page with redirect `http://localhost:42813/callback`, the loopback server receives
   the code, and the app stores a `ConnectedAccount` after the short-lived→long-lived
   token exchange and `/me` call.
4. **Upload smoke test**: compose a short MP4 Reel, toggle `shareToFeed`, publish;
   confirm progress events render, the container reaches `FINISHED`, `media_publish`
   succeeds, and the Reel appears on the connected account.
5. **Cancellation smoke test**: start an upload, cancel mid-transfer, confirm the Rust
   loop returns promptly via the cancellation flag.
6. **Token refresh**: simulate a near-expiry `expiresAt` in a stored credential and
   confirm `getValidAccessToken` calls `refreshLongLivedToken` and persists the result.

## Critical files

- `src/platforms/instagram/InstagramAuth.ts` (new)
- `src/platforms/instagram/instagramUploadCommand.ts` (new)
- `src-tauri/src/commands/instagram_upload.rs` (new)
- `src-tauri/src/commands/oauth.rs` (add fixed-port command)
- `src/platforms/instagram/InstagramAdapter.ts` (implement)
- `src/platforms/instagram/InstagramSettingsPanel.tsx` (implement)
- `src-tauri/src/lib.rs` (register new command/state)
- `src/platforms/auth.ts` (wire `InstagramAuth`)
