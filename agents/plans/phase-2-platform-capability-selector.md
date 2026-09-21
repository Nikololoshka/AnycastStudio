# Implementation Plan: Phase 2 — Platform Capability Model & Selector

## Context

Phases 0–1 are implemented and committed (`51fdf37`, `dfac614`): domain types,
store wiring, file/thumbnail input, and the composer form all work end-to-end
with no platform logic. Per
`agents/plans/agents-prd-prd-md-fyi-create-implmeneta-binary-quilt.md`, Phase 2
is the last stub-only increment before real auth/upload work starts in Phase 3:
it replaces the hardcoded `PlatformSelector` checkbox list with one driven by
real per-platform `PlatformCapabilities` + `accountsSlice` connection state
(PRD §9, §13), and adds an empty platform-settings tab shell (PRD §10) for
later phases to fill in.

Today `src/platforms/*/[Platform]Adapter.ts` all throw `"not implemented"`
from `getCapabilities()`, `accountsSlice` has `reducers: {}`, and
`PlatformSelector` renders a local hardcoded `PLATFORMS` array with plain
checkboxes and no connection status. No upload/auth logic is added in this
phase — `Connect` stays a disabled placeholder until Phase 3.

---

## 1. Real `getCapabilities()` per platform

Files: `src/platforms/{youtube,x,instagram,tiktok}/[Platform]Adapter.ts`.

Replace the `throw new Error("not implemented")` body of `getCapabilities()`
in each adapter with a real `PlatformCapabilities` literal, based on current
public API docs. Leave `validate`/`upload`/`publish`/`schedule` as stubs —
those land with each platform's adapter phase (5/6).

Best-available limits as of this plan (flag each for re-verification against
current docs when that platform's adapter phase starts, since API limits
change):

- **YouTube** (Data API v3, resumable upload): `scheduling: "native"`
  (`status.publishAt`), `title`/`description`/`hashtags`: `true`,
  `drafts: true` (`status.privacyStatus: "private"` acts as a draft),
  `maxFileSize: 128 * 1024 ** 3` (128GB), `supportedMimeTypes` covering the
  documented list (`video/mp4`, `video/quicktime`, `video/x-msvideo`,
  `video/x-ms-wmv`, `video/x-flv`, `video/3gpp`, `video/webm`, `video/mpeg`).
- **X** (media upload + posts API): `scheduling: "unsupported"` (no public
  API for scheduled posts outside the paid web UI feature, which isn't
  API-exposed), `title: false` (no separate title field), `description: true`
  (post text), `hashtags: true` (inline in post text), `drafts: false`,
  `maxFileSize: 512 * 1024 ** 2` (512MB video), `supportedMimeTypes: ["video/mp4", "video/quicktime"]`.
- **Instagram** (Graph API content publishing, container→publish): treat
  `scheduling: "local"` (the API's own scheduled-publish support is narrow/
  Page-dependent — safer to drive scheduling from our own local scheduler
  than assume native support; revisit in Phase 6/7), `title: false`,
  `description: true` (caption), `hashtags: true` (inline in caption),
  `drafts: false`, `maxFileSize: 1024 ** 3` (1GB, Reels), `supportedMimeTypes: ["video/mp4", "video/quicktime"]`.
- **TikTok** (Content Posting API): `scheduling: "unsupported"` (scheduled
  direct-post is a restricted/early-access capability, don't assume general
  availability), `title: false`, `description: true` (caption), `hashtags: true`
  (inline in caption), `drafts: true` (API supports posting to inbox as
  draft), `maxFileSize: 4 * 1024 ** 3` (4GB), `supportedMimeTypes: ["video/mp4", "video/quicktime", "video/webm"]`.

## 2. `accountsSlice`: real reducers, still no auth

File: `src/features/accounts/accountsSlice.ts` (currently `reducers: {}`).

Add reducers so the slice is functionally complete for Phase 3 to call into
without touching this file again:

- `setAccount(account: ConnectedAccount)` — upsert into `items` keyed by `account.id`
- `removeAccount(accountId: string)` — delete from `items`

Add a selector helper (e.g. `selectAccountByPlatform` in `accountsSlice.ts` or
a small `selectors.ts` alongside it) that finds the connected account, if any,
for a given `Platform` — `PlatformSelector` needs "is this platform connected"
by platform id, not by account id. Export both actions and the selector from
`src/features/accounts/index.ts` alongside the existing reducer export.

No thunks, no adapter calls yet — Phase 3 wires `connectPlatform`/
`disconnectPlatform` thunks against these reducers.

## 3. Capability lookup helper

New file: `src/platforms/capabilities.ts`.

A small `getCapabilitiesFor(platform: Platform): PlatformCapabilities` that
maps each `Platform` id to its adapter's `getCapabilities()` (instantiate each
adapter once, e.g. a `const adapters: Record<Platform, PlatformAdapter>`
lookup). This keeps `PlatformSelector` and the future settings tabs from
importing each adapter class directly, and gives Phase 3+ a single place to
extend when adapters stop being stateless.

## 4. `PlatformSelector`: capability + connection driven

File: `src/components/PlatformSelector/PlatformSelector.tsx` (currently a
static `PLATFORMS` array with plain checkboxes, per Phase 1's scope note that
this is deferred here).

- Replace the hardcoded `PLATFORMS` array with a fixed `Platform[]` id list
  (`["youtube", "x", "instagram", "tiktok"]`, still the only place platform
  ids are enumerated — capability data now comes from step 3, not from here)
  plus a small display-name map for labels.
- For each platform, read `getCapabilitiesFor(platform)` and the connection
  state via `selectAccountByPlatform` from `accountsSlice`.
- Render per PRD §9: checkbox + label, then connection status line —
  `"✓ Connected"` with the account's `displayName` when a `ConnectedAccount`
  exists, otherwise `"Not connected"` plus a `Connect` button. The button
  stays `disabled` in this phase (`onClick` no-op) — Phase 3 wires it to
  `connectPlatform`.
- Keep the existing `togglePlatform` checkbox behavior from Phase 1 unchanged.

## 5. Platform-settings tab shell

New component: `src/components/PlatformSettingsTabs/` (`PlatformSettingsTabs.tsx`

- `index.ts`, matching the existing `PlatformSelector` folder shape).

* MUI `Tabs`/`Tab` per PRD §10 mockup, one tab per platform in
  `composer.selectedPlatforms` (platforms not selected for this publication
  don't need a settings tab yet).
* Each tab renders an empty placeholder panel component per platform
  (`src/platforms/{platform}/[Platform]SettingsPanel.tsx`, a thin functional
  component returning a "No settings yet" `Typography` placeholder) — these
  become real forms as each platform's adapter phase lands (5/6), so the tab
  container never needs to change again.
* Mount `<PlatformSettingsTabs />` in `ComposerScreen.tsx` directly below
  `<PlatformSelector />`.

## 6. `composer` no other changes

No `composerSlice` changes needed this phase — `platformSettings` already
exists in state (Phase 1) and `setPlatformSettings` already exists as an
action; the settings panels just don't dispatch anything real yet.

---

## Verification

- `npm run tauri dev`: `PlatformSelector` shows all four platforms as "Not
  connected" (no accounts exist yet) with a disabled `Connect` button each,
  and checkboxes still toggle `composer.selectedPlatforms` as in Phase 1.
- Manually dispatch `accounts.setAccount(...)` from Redux DevTools for one
  platform; confirm that platform's row switches to "✓ Connected" with the
  right display name, with no code change required (proves the selector is
  state-driven, not hardcoded).
- Select a platform in the checklist, confirm a matching tab appears in
  `PlatformSettingsTabs`; deselect it, confirm the tab disappears.
- `npx tsc --noEmit` passes with all four adapters' `getCapabilities()`
  returning real literals instead of throwing.
