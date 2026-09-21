# TikTok upload implementation (mirroring YouTube)

## Context

YouTube upload/publish is already implemented (`src/platforms/youtube/`, `src-tauri/src/commands/youtube_upload.rs`). TikTok is scaffolded but non-functional: `TikTokAdapter.ts` implements `PlatformAdapter` with real `getCapabilities()` but every other method throws `not implemented`, and `auths.tiktok` is a `notImplemented('tiktok')` stub. It's already wired into `src/platforms/capabilities.ts`, `src/platforms/auth.ts`, and the composer's `PlatformTab.tsx`. This plan fills in the stub so TikTok upload works end-to-end against TikTok's **sandbox/unaudited** Content Posting API using the `FILE_UPLOAD` (direct chunked PUT) transport — the only viable transport for a local desktop app with no public file host.

Decisions were pressure-tested against TikTok's actual API docs (see research notes in `agents/plans/i-have-impl-for-smooth-steele-agent-*.md`) and against the existing YouTube implementation as the pattern to follow, deviating only where TikTok's protocol genuinely differs.

## Key differences from YouTube worth calling out

- TikTok's token exchange requires `client_secret` even with PKCE (same trust model as YouTube's existing confidential-client embed — no new posture needed).
- Sandbox apps are **forced to `SELF_ONLY` visibility** regardless of requested `privacy_level` — so the settings panel should not offer a privacy selector at all right now (it would be a dead control).
- TikTok's chunk PUT (to the pre-signed `upload_url`) needs **no Authorization header** — unlike YouTube's resumable-session PUT. Only the init call is bearer-authenticated.
- Because nothing is bearer-authenticated during chunking, a 401/403 can only happen at the init step, before any bytes are sent. There's no byte-offset-to-resume concept to build — on that failure, refresh the token and retry the whole upload call from scratch (no session/offset payload needed).
- TikTok's Direct Post flow auto-publishes as part of init+upload; there's no separate "flip to public" call like YouTube's `publish()`. But success/failure is only knowable via a follow-up status poll (`/v2/post/publish/status/fetch/`), so the adapter must poll (bounded, ~5 min timeout) before marking the publication `completed`.

## Files to add

### `src/platforms/tiktok/TikTokAuth.ts`
Implements `PlatformAuth`, mirrors `src/platforms/youtube/YouTubeAuth.ts`:
- Reuse `src/services/auth/pkce.ts`, `oauthLoopback.ts`, `SecureStorage.ts` as-is (already platform-agnostic).
- `AUTH_ENDPOINT`/`TOKEN_ENDPOINT`/`REVOKE_ENDPOINT` for `https://www.tiktok.com/v2/auth/authorize/` and `https://open.tiktokapis.com/v2/oauth/{token,revoke}/`.
- `SCOPES = 'user.info.basic,video.publish'`.
- `clientKey()`/`clientSecret()` read `import.meta.env.VITE_TIKTOK_CLIENT_KEY` / `VITE_TIKTOK_CLIENT_SECRET` (throw if unset) — note TikTok's term is "client_key", not "client_id".
- `connect()`: loopback server → PKCE → open authorize URL → await callback → exchange code (`client_key` + `client_secret` + `code_verifier`) → fetch `/v2/user/info/` (`user.info.basic`) to get `open_id`/`display_name` for `ConnectedAccount { id: 'tiktok:' + openId, ... }` → `storeCredential`.
- `disconnect()`: best-effort revoke, then `deleteCredential`.
- `getValidAccessToken(accountId)`: same expiry-buffer-then-refresh pattern as `YouTubeAuth`.

### `src/platforms/tiktok/tiktokUploadCommand.ts`
Mirrors `youtubeUploadCommand.ts`:
- Opens a Tauri `Channel<UploadProgressEvent>`, invokes `upload_video_tiktok` with `{ uploadId, path, mimeType, accessToken, postInfo }`.
- `cancelTikTokUpload(uploadId)` → `invoke('cancel_tiktok_upload', ...)`.
- On an `Authentication`-type `PublicationError` from Rust, refresh the token (`getAccessToken()`) and retry the **entire** `invokeUpload` call (no offset/session state to thread through — simpler than YouTube's resume logic).
- After the Rust call resolves with a `publishId`, poll TikTok's status endpoint (new helper, e.g. `pollPublishStatus(accessToken, publishId)`): backoff (10s → 30s → 60s → 120s, capped), stop on `PUBLISH_COMPLETE` (resolve) or `FAILED` (reject with `PublicationError{type:'platform', message: fail_reason}`), or after ~5 minutes total (reject with a timeout `PublicationError{type:'platform'}` telling the user to check TikTok manually).

### `src/platforms/tiktok/TikTokAdapter.ts` (replace stub methods)
- `validate()`: file size ≤ capabilities.maxFileSize (4GB), mime type in capabilities list — no title check (capabilities already say `title: false`).
- `upload()`: build `postInfo` from `publication.settings` — `privacy_level: 'SELF_ONLY'` (hardcoded, not read from settings), `disable_duet`/`disable_comment`/`disable_stitch` (read from settings, default false), `title` = the publication's `description` text (TikTok's caption field). Call `uploadVideoToTikTok(...)`, wrap errors via `toPublicationError`.
- `publish()`: no-op / trivially resolves — TikTok already published as part of `upload()`'s init+chunk+status-confirm sequence.
- `schedule()`: leave unimplemented — capabilities already declare `scheduling: 'unsupported'`.

### `src/platforms/tiktok/TikTokSettingsPanel.tsx` (replace stub)
Minimal UI: a read-only note explaining sandbox posts are private-only, plus three toggles (disable duet / comment / stitch) writing into `publication.settings`. No privacy selector, no disclosure-flag fields (deferred until pursuing app audit).

### `src-tauri/src/commands/tiktok_upload.rs`
Mirrors `youtube_upload.rs`'s shape:
- `initiate_video_init()`: `POST https://open.tiktokapis.com/v2/post/publish/video/init/` with `Authorization: Bearer {access_token}`, JSON body `{ post_info, source_info: { source: "FILE_UPLOAD", video_size, chunk_size, total_chunk_count } }` → parse `publish_id` + `upload_url` from response body (not headers, unlike YouTube's `Location` header).
- On 401/403 from this call: return `UploadError::Authentication` with **no** resume payload (nothing sent yet) — TS retries the whole command.
- Chunk loop: chunk size in the 5–64MB range (e.g. 10MB, matching existing `read_chunk` helper in `filesystem.rs`), final chunk = remainder (up to 128MB allowed); PUT each chunk to the full `upload_url` (including its query string) with `Content-Type`, `Content-Range: bytes {start}-{end}/{total}`, `Content-Length` — **no** `Authorization` header.
- Reuse/adapt the existing `with_retry()` backoff helper (network errors, 429, 5xx) for chunk PUTs.
- Progress reporting via `Channel<UploadProgressEvent>`, same shape as YouTube's.
- Cancellation via the same `UploadCancellations` Tauri-managed state pattern (checked each chunk iteration).
- Commands: `upload_video_tiktok`, `cancel_tiktok_upload` — register in `src-tauri/src/commands/mod.rs` and the `invoke_handler` list in `src-tauri/src/lib.rs`.

## Files to modify

- `src/platforms/auth.ts`: replace `auths.tiktok = notImplemented('tiktok')` with `new TikTokAuth()`.
- `src/vite-env.d.ts`: add `VITE_TIKTOK_CLIENT_KEY` and `VITE_TIKTOK_CLIENT_SECRET` to `ImportMetaEnv`.
- `.env.local` (not committed): document the two new TikTok vars are required; consider adding a `.env.example` listing all required var names (none currently exists) without values.
- `src-tauri/src/commands/mod.rs` / `src-tauri/src/lib.rs`: register the new Rust command module and its two commands.

## Out of scope for this pass

- Privacy-level selection UI, disclosure toggles (`brand_content_toggle`, `brand_organic_toggle`, `is_aigc`) — meaningless until the app passes TikTok's audit for public posting.
- The upload-to-inbox (`video.upload`) flow — Direct Post (`video.publish`) only.
- Any secret-holding relay/proxy — same embedded-secret trust model as YouTube is accepted for now.

## Verification

1. `npx tsc --noEmit` and `npm run lint` clean.
2. Create a TikTok Developer sandbox app (Login Kit + Content Posting API), add this machine's TikTok account to the sandbox's target users, set `VITE_TIKTOK_CLIENT_KEY`/`VITE_TIKTOK_CLIENT_SECRET` in `.env.local`.
3. `npm run tauri dev`: connect a TikTok account (verify loopback OAuth completes and the credential lands in the OS keyring, not Redux/localStorage), pick a small test video, toggle duet/comment/stitch, upload, and confirm: progress updates live, the publication reaches `completed` only after the status poll reports `PUBLISH_COMPLETE`, and the video shows up privately on the TikTok test account.
4. Exercise failure paths manually where feasible: cancel mid-upload (`cancel_tiktok_upload` fires, upload stops), and a deliberately invalid/expired token to confirm the whole-call retry-after-refresh path.
5. Disconnect the account and confirm the keyring entry is removed and revoke is attempted.
