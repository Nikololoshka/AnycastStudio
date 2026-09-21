# Implementation Plan: Multi-Platform Video Uploader (MVP)

## Context

`agents/prd/PRD.md` defines the full MVP for a Tauri + React desktop app that
publishes one video to YouTube, X, Instagram, and TikTok in parallel. The repo
already has a scaffold (`472214f`/`65c6195`) whose folder layout and type
stubs mirror the PRD's suggested architecture exactly (`src/domain`,
`src/platforms`, `src/features`, `src/services`, `src-tauri/src/commands`),
but almost everything is an unimplemented stub: empty Redux slices, a
`PlatformAdapter` interface with no implementations, Rust commands that
`Err("not implemented")`, no persistence, no scheduler, no auth flows.

This plan sequences the build so each phase produces a runnable, testable
increment, uses YouTube as the reference vertical slice (most mature public
API, resumable upload + native scheduling), and wires real OAuth apps/API
credentials for all four platforms per the user's decisions. Persistence uses
`tauri-plugin-store` (JSON) for app state/history and Windows Credential
Manager (via the Rust `keyring` crate) for tokens only, matching PRD §32/§37.

---

## Phase 0 — Foundations (domain types, store wiring, file access)

- Flesh out `src/domain/{video,platform,publication}/types.ts` — these are
  already ~correct per the PRD; add any missing pieces (`UploadProgress` from
  §19, `PublicationTask`/`PublicationsState` from §20).
- Wire `src/app/store/index.ts` to combine `accounts`, `composer`,
  `publications`, `settings` reducers (slices already exist, mostly empty).
- Implement `src/services/filesystem/FileReader.ts` against Tauri: a
  `TauriFileReader` that calls Rust chunked-read commands (§23) instead of
  loading full files into JS memory.
- Rust side (`src-tauri/src/commands/filesystem.rs`): implement
  `get_file_metadata` (size, mime sniffing) and add `read_file_chunk`
  (offset/size → `Vec<u8>`) as declared in PRD §22. Register new commands in
  `src-tauri/src/commands/mod.rs` / `lib.rs` invoke_handler.
- Add `tauri-plugin-store` dependency (Cargo.toml + package.json) and a
  `src/services/persistence` module wrapping it for settings/history/
  scheduled-publications reads & writes (PRD §32).
- Add the `keyring` crate to `src-tauri/Cargo.toml`; implement
  `src-tauri/src/commands/secure_storage.rs` (`store_credential`,
  `get_credential`, `delete_credential`) against Windows Credential Manager.
  Enforce §37: only these Tauri commands ever touch secrets; Redux never
  stores raw tokens.

**Verification:** `npm run tauri dev` launches; a temporary debug button can
call `get_file_metadata`/`read_file_chunk` on a sample video and log results
to confirm the Rust↔TS bridge and store plugin work before UI work begins.

---

## Phase 1 — Video input & composer UI (no platforms yet)

- `src/components/VideoDropZone`: implement drag-and-drop + native file
  picker (`@tauri-apps/plugin-dialog`), populate `VideoFile` (name, size,
  mimeType) via the Phase-0 file services; generate a thumbnail (ffmpeg via
  Rust sidecar, or a `<video>` canvas-capture fallback in the webview if
  native isn't ready yet — decide during implementation, default to the
  webview approach to keep Rust thin per §22).
- Extend `composerSlice` with actions: `setVideo`, `clearVideo`, `setTitle`,
  `setDescription`, `setHashtags`, `setScheduledAt`, `togglePlatform`,
  `setPlatformSettings`.
- Implement hashtag normalization (PRD §8: `"#a #b"` and `"a, b"` → identical
  `string[]`) as a pure domain util in `src/domain/publication` (e.g.
  `normalizeHashtags.ts`), unit-testable in isolation.
- Build `ComposerScreen.tsx` layout per PRD §6 (video card, title/description/
  hashtags, platform checklist, publish-now/schedule radio, Publish button),
  using MUI components already in `package.json`.

**Verification:** Manually drag a video in dev mode, confirm metadata/
thumbnail render and Redux state updates (Redux DevTools or a temp state
dump).

---

## Phase 2 — Platform capability model & selector

- Each platform module (`src/platforms/{youtube,x,instagram,tiktok}`) exports
  a `capabilities: PlatformCapabilities` object (PRD §13) reflecting real
  documented limits (max file size, mime types, scheduling support: YouTube
  "native", X/Instagram/TikTok per actual API docs — verify during
  implementation, likely "unsupported" or "local" where no native schedule
  API exists).
- `src/components/PlatformSelector`: render checkboxes + connection status
  driven by `accountsSlice` + capabilities, not hardcoded platform lists (§9,
  §13).
- Add platform-settings tab UI (PRD §10) as a thin shell now (empty per-tab
  panels), to be filled in as each adapter lands.

**Verification:** Toggling platforms updates `composer.selectedPlatforms`;
UI reflects capability-driven differences (e.g., disable schedule option for
an "unsupported" platform) even before real adapters exist.

---

## Phase 3 — Auth abstraction + YouTube OAuth (reference slice)

- Implement `PlatformAuth` for YouTube (`src/platforms/youtube/YouTubeAuth.ts`):
  OAuth 2.0 (Google) authorization-code + PKCE flow, using Tauri's
  `shell.open`/deep-link or an embedded webview flow to capture the redirect,
  refresh-token handling. Store the access/refresh token only via the Phase-0
  secure-storage Tauri commands; `accountsSlice` stores only
  `ConnectedAccount` (id, platform, displayName, avatarUrl) — never tokens
  (§24, §37).
- `src/features/accounts/accountsSlice.ts`: `connectPlatform`,
  `disconnectPlatform` thunks calling the adapter's `PlatformAuth`, plus
  `AccountsSettings` UI section (§35 Accounts, §24 mockup) with
  Connect/Disconnect actions.
- User must supply a Google Cloud OAuth client ID/secret (YouTube Data API
  v3) before this phase can be exercised against the real API — flag this as
  an external dependency/config step (e.g., `.env`/Tauri config value, never
  hardcoded).

**Verification:** Click "Connect" for YouTube, complete real OAuth consent,
confirm `ConnectedAccount` appears in Redux and the token lands in Windows
Credential Manager (not in Redux/localStorage/logs — grep app logs to
confirm no token strings appear, per §36).

---

## Phase 4 — YouTube adapter: validate → upload → publish

- Implement `YouTubeAdapter implements PlatformAdapter`
  (`src/platforms/youtube/YouTubeAdapter.ts`):
  - `validate`: file size/mime/duration checks against `getCapabilities()`
    and required title.
  - `upload`: resumable upload session against YouTube Data API v3 using the
    Phase-0 chunked `FileReader` (never loads the whole file into memory),
    reporting `UploadProgress` (§19).
  - `publish`: set video metadata (title/description/hashtags→tags,
    visibility) via `videos.update`.
  - `schedule`: native scheduled publish (`status.publishAt`) since YouTube
    capability is `"native"`.
- Wire an `UploadManager` application service (`src/services/upload`) that
  drives the common lifecycle (§17: validate→prepare→upload→process→publish/
  schedule→completed) calling into whichever adapter, while allowing an
  adapter to internally diverge from that lifecycle.
- `src/components/UploadProgress`: per-platform progress bar / status text
  bound to `publicationsSlice` state, supporting indeterminate progress when
  an adapter can't report real byte progress (§19).

**Verification:** Full flow: connect YouTube → add real short test video →
publish now → confirm it appears on the connected YouTube channel with
correct title/description/tags, and progress UI updates live.

---

## Phase 5 — Parallel publishing, retry, cancellation

- `src/features/publications/publicationsSlice.ts`: model `PublicationTask`
  keyed by publication id, each with per-platform `PlatformPublication`
  status/progress/error (§14, §15, §20).
- Implement the publish orchestrator (likely in `src/services/upload` or a
  new `src/services/publisher`): on "Publish" click, create one task per
  selected platform and run them via `Promise.allSettled` (§18), respecting
  a configurable `maxConcurrentUploads` (§34) — a small concurrency-limited
  queue (e.g. a tiny in-house semaphore; no new dependency needed).
- Cancellation: each adapter's `upload` must accept an `AbortSignal` (extend
  `PlatformAdapter.upload` signature) so cancelling one platform's task
  aborts only that HTTP request (§29).
- Retry: exponential backoff for transient errors only (network/rate-limit/
  server) per §28; classify errors via the existing `ErrorType` union;
  manual "Retry" re-runs only the failed platform's task, never re-publishing
  already-completed ones (§41 Retry acceptance criteria).
- Build the monitoring view (§30) and error UI (§27: human-readable message +
  "Reconnect"/"Retry" actions + a "Details" expando for technical info).

**Verification:** Select all four platforms with only YouTube fully wired
(others temporarily stubbed to simulate success/failure), confirm one
forced/simulated failure doesn't stop the others, and Retry only restarts the
failed one.

---

## Phase 6 — Remaining adapters: X, Instagram, TikTok

Repeat the Phase 3+4 pattern per platform, in this order: X, then Instagram,
then TikTok (largest to smallest API complexity risk is a judgment call to
revisit once YouTube is done — flag for confirmation if priorities shift).
For each:

- `PlatformAuth` (platform-specific OAuth app; user must supply each
  platform's developer credentials).
- `PlatformAdapter` (`validate`/`upload`/`publish`/optional `schedule`)
  against that platform's real documented API (media upload endpoints differ
  significantly: X media/tweet split, Instagram Graph API container+publish
  two-step flow, TikTok Content Posting API's own upload+publish flow).
- Platform-specific settings tab content (§10) driven by real API fields
  (e.g., TikTok privacy/duet/stitch, Instagram media type/cover, X reply
  settings).
- Capability object refined per real platform documentation (scheduling is
  very likely `"unsupported"` or `"local"` for at least Instagram/TikTok —
  confirm against current API docs during implementation).

**Verification:** For each platform, repeat the Phase-4-style manual
end-to-end publish test against a real test account.

---

## Phase 7 — Scheduling (native + local fallback)

- `src/services/scheduler`: given a `Publication` with `scheduledAt`, resolve
  per-platform strategy from `PlatformCapabilities.scheduling` (§12):
  - `"native"` → call the adapter's `schedule()`.
  - `"local"` → register with a local scheduler that, while the app is
    running, fires upload+publish at the scheduled UTC time (persisted via
    Phase-0 store so it survives restarts within the MVP's "app must be
    running" constraint, §33).
  - `"unsupported"` → surface clearly in the UI, don't allow scheduling that
    platform.
- Composer scheduling UI (§11): date/time + timezone picker, converting local
  time to UTC `scheduledAt` before it enters domain state.
- On app startup, restore any persisted scheduled/in-progress publications
  and re-arm local scheduled tasks (§41 Persistence acceptance criteria).

**Verification:** Schedule a near-future publication to YouTube (native) and
to a `"local"`-capability platform; confirm YouTube shows scheduled status in
its API response and the local one fires at the right UTC instant; restart
the app before it fires and confirm it still fires afterward.

---

## Phase 8 — Validation, history, settings polish

- Global + per-platform validation pass before publish (§26), surfaced per
  platform/field (mirroring the §26 example table).
- Publication history (§31): persist completed/failed publication summaries
  (thumbnail, title, date, platforms, status) via Phase-0 persistence;
  history list + detail view showing per-platform results.
- Settings screens (§35): General (language/theme/default hashtags),
  Accounts (already built in Phase 3), Upload (concurrency/retry count/chunk
  size/bandwidth limit — wire concurrency & retry count into the Phase-5
  orchestrator), Scheduler (timezone, startup behavior).
- Structured logging (§36) via a small logger wrapper used across services;
  audit that no adapter/auth code ever logs tokens/secrets/headers.

**Verification:** Run the full PRD §43 Definition-of-Done flow once, end to
end, against real accounts on all four platforms, and confirm history/
settings persist across an app restart.

---

## Cross-cutting notes

- Keep the dependency direction from PRD §21/§42 strict: UI → Redux →
  services (`UploadManager`, scheduler, publisher) → platform adapters →
  platform APIs → Tauri → Rust. Do not let adapters reach into Rust directly
  except through the shared `FileReader`/secure-storage services.
- Every new Tauri command must be added to the explicit `invoke_handler`
  allowlist in `src-tauri/src/lib.rs` (§37.7) — no blanket exposure.
- Each phase after Phase 0 is independently demoable; if priorities change
  mid-build (e.g., a different platform should come second), that only
  affects Phase 6's ordering, not the earlier architecture.
