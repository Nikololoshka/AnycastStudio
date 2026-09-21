# Implementation Plan: Phase 3 — Auth Abstraction + YouTube OAuth

## Context

`agents/plans/agents-prd-prd-md-fyi-create-implmeneta-binary-quilt.md` Phase 3
calls for a real `PlatformAuth` implementation for YouTube (OAuth2+PKCE),
account connect/disconnect wired through Redux, and tokens stored only via
the Phase-0 secure-storage Tauri commands — never in Redux/localStorage/logs.
Phases 0–2 are done: `SecureStorage.ts` + `secure_storage.rs` (keyring-backed)
exist, `accountsSlice` holds `ConnectedAccount` records, `PlatformAuth`/
`PlatformAdapter` interfaces exist, and `YouTubeAdapter` is a stub. Nothing
OAuth-specific exists yet — this phase builds it for YouTube only, per the
plan's "YouTube as reference vertical slice" strategy; X/Instagram/TikTok
repeat the pattern in Phase 6.

Two decisions were confirmed with the user:

- **Redirect capture**: system browser + a local loopback HTTP server (Rust),
  matching Google's own recommended flow for installed apps — a "Desktop app"
  OAuth client type needs no client secret, and this avoids deep-link OS
  registration or loading Google's login inside an app-controlled webview.
- **Client ID config**: a build-time `VITE_YOUTUBE_CLIENT_ID` in `.env.local`
  (already covered by the existing `*.local` gitignore rule) — no UI needed
  yet; the user supplies their own Google Cloud OAuth client ID before this
  phase can be exercised against the real API.

There is no router/Settings screen yet (`src/app/router/index.ts` is an empty
stub, `App.tsx` renders only `ComposerScreen`). Rather than build routing
early, this phase adds a minimal MUI `Tabs` switch in `App.tsx` between
"Composer" and "Accounts" — enough to reach the new Accounts UI without
pulling routing work forward.

---

## 1. Rust: loopback OAuth callback server

New `src-tauri/src/commands/oauth.rs`, using the `tiny_http` crate (add to
`Cargo.toml`) for a minimal, synchronous, dependency-light HTTP server —
keeps Rust to system-level plumbing only, no OAuth/PKCE logic in Rust:

- `start_oauth_callback_server() -> Result<u16, String>`: binds
  `tiny_http::Server` to `127.0.0.1:0` (OS-assigned free port), spawns a
  `std::thread` that blocks on `server.recv()` for exactly one request,
  parses its query string, and sends the result through a `tokio::sync::oneshot`
  channel held in managed Tauri state (`Mutex<Option<oneshot::Receiver<...>>>`).
  Responds to the browser request with a small static "you can close this
  window" HTML body. Returns the bound port immediately so the caller can
  build the `redirect_uri`.
- `await_oauth_callback(timeout_secs: u64) -> Result<OAuthCallbackParams, String>`:
  takes the receiver out of state and awaits it with `tokio::time::timeout`,
  returning `{ code, state }` or an error (timeout / user closed browser /
  malformed callback).

Register both in `commands/mod.rs`, the `invoke_handler` in `src-tauri/src/lib.rs`,
and add the `.manage(OAuthCallbackState::default())` call in `run()`.

## 2. TypeScript: generic OAuth/PKCE utilities (reusable by future platforms)

- `src/services/auth/pkce.ts`: `generateCodeVerifier()` and
  `generateCodeChallenge(verifier)` using `crypto.getRandomValues` +
  `crypto.subtle.digest("SHA-256", ...)` (Web Crypto, available in the Tauri
  webview) + base64url encoding.
- `src/services/auth/oauthLoopback.ts`: thin wrapper invoking the two Rust
  commands above (`startOAuthCallbackServer`, `awaitOAuthCallback`).

## 3. YouTube auth adapter

`src/platforms/youtube/YouTubeAuth.ts` implements `PlatformAuth`
(`src/services/auth/PlatformAuth.ts`):

- `connect()`:
  1. `startOAuthCallbackServer()` → port; build
     `redirect_uri = http://127.0.0.1:<port>/callback`.
  2. Generate PKCE verifier/challenge; build the Google authorization URL
     (`https://accounts.google.com/o/oauth2/v2/auth`) with
     `client_id=import.meta.env.VITE_YOUTUBE_CLIENT_ID`, `scope=
https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly`,
     `response_type=code`, `code_challenge`, `code_challenge_method=S256`,
     `access_type=offline`, `prompt=consent`.
  3. Open it via `@tauri-apps/plugin-opener`'s `openUrl` (already a
     dependency; confirm `opener:default` capability covers `allow-open-url`
     in `src-tauri/capabilities/default.json`, add the explicit permission if
     not).
  4. `awaitOAuthCallback()` → `{ code }`.
  5. Exchange the code at `https://oauth2.googleapis.com/token` (POST,
     `application/x-www-form-urlencoded`, includes `code_verifier`, no
     secret) via `fetch` → `{ access_token, refresh_token, expires_in }`.
  6. Fetch the channel via YouTube Data API
     (`GET /youtube/v3/channels?part=snippet&mine=true`) for `displayName`/
     `avatarUrl`.
  7. `storeCredential(accountId, JSON.stringify({ accessToken, refreshToken, expiresAt }))`
     via the existing `SecureStorage.ts` — Redux only ever receives the
     returned `ConnectedAccount`.
  8. Return the `ConnectedAccount`.
- `disconnect(accountId)`: best-effort token revoke
  (`POST https://oauth2.googleapis.com/revoke`), then `deleteCredential`.
- `getAccount()`: not required for this phase's flow (accounts are read from
  Redux state, not re-fetched); implement as a thin re-fetch of the channel
  info using a stored token, reusing step 6 above, for parity with the
  interface.
- Add `getValidAccessToken(accountId)` (adapter-specific, not on the
  `PlatformAuth` interface) that reads the stored credential, refreshes via
  the token endpoint's `refresh_token` grant if `expiresAt` has passed, and
  re-stores the updated credential — this is what Phase 4's `upload()` will
  call; stub it in now so Phase 4 doesn't need to touch auth code.

## 4. Redux + UI wiring

- `src/features/accounts/accountsSlice.ts`: add `connectPlatform` and
  `disconnectPlatform` `createAsyncThunk`s that look up the platform's
  `PlatformAuth` via a new small registry `src/platforms/auth.ts` (mirrors
  `src/platforms/capabilities.ts`'s `adapters` map — YouTube wired to
  `YouTubeAuth`, X/Instagram/TikTok throwing "not implemented" until Phase 6),
  call `connect()`/`disconnect()`, and dispatch `setAccount`/`removeAccount`
  on success. Track per-platform `pending`/`error` in slice state for the UI.
- `src/features/accounts/AccountsSettings.tsx`: one row per `Platform` (list
  from `src/domain/platform/types.ts`), showing connected state from
  `selectAccountByPlatform`, a Connect/Disconnect button dispatching the
  thunks, and an inline error message on failure.
- `src/App.tsx`: wrap `ComposerScreen` and the new `AccountsSettings` in an
  MUI `Tabs`/`Tab` pair ("Composer" / "Accounts") — no new routing
  infrastructure.

## 5. Config

- `.env.local` (gitignored via existing `*.local` rule) with
  `VITE_YOUTUBE_CLIENT_ID=...`; add `.env.local.example` (committed) as the
  documented placeholder, and a short README/CLAUDE.md note that a Google
  Cloud "Desktop app" OAuth client with the YouTube Data API v3 enabled is
  required before this phase can be exercised.

---

## Verification

1. `npm run tauri dev`, switch to the Accounts tab, click "Connect" under
   YouTube.
2. Confirm the system browser opens Google's real consent screen, and after
   approving, the browser shows the loopback "you can close this window"
   page and the app tab reflects a connected account (avatar + channel name)
   without any manual step.
3. Inspect Redux state (DevTools) — `accounts.items` holds only `id`,
   `platform`, `displayName`, `avatarUrl`; no token fields anywhere in Redux.
4. Open Windows Credential Manager, confirm an entry under the `multiposter`
   service for the account id, holding the JSON credential blob.
5. Grep app logs/console output for the raw access/refresh token strings —
   confirm none appear (PRD §36).
6. Click "Disconnect", confirm the Credential Manager entry is removed and
   the UI reverts to a "Connect" state.
