# Main UI Redesign: 3-Column Single-Window Layout

## Context

The current UI is two flat MUI tabs at the top of the window ("Composer" / "Accounts") with no chrome, no persistent overview, and a single long scrolling form. This doesn't scale as more platforms come online and gives no at-a-glance view of what's about to be published or what already happened. The user wants one window that uses the full available space: history on the left (placeholder for now), an editable composer with per-platform tabs in the center, and a live summary + publish action + status on the right, topped by a simple AppBar. This plan restructures the existing screens/components into that layout without touching business logic, adapters, or adding dependencies.

All design decisions below were confirmed with the user through a grilling session; nothing here should be re-litigated during implementation.

## Confirmed Decisions

- Single window, no router. AppBar (hardcoded "Multiposter" + version via `getVersion()`) on top, 3-column body below: History ~20% | Composer ~55% | Summary ~25%, fixed proportions (no resizable dividers, no new dependency).
- Window stays 800×600 default in `tauri.conf.json`; it's already resizable by Tauri's default (no `resizable: false` present), so **no config change is required** for resizing — verified by reading the file. Optional cosmetic fix: `productName`/window `title` still say `"scaffold"`, could be updated to `"Multiposter"` while in there (not required).
- Left column: **static placeholder only** — header "History" + "No history yet." text. No data wiring to `publicationsSlice`, no list, no click behavior, no modal. Fully deferred.
- Center column: header + MUI Tabs `Common | YouTube | X | TikTok | Instagram`, always all 5 visible.
  - Common tab: video selector, title, description, hashtags, and a publish-now/schedule picker — reuse existing logic verbatim.
  - Each platform tab (always rendered, not conditional on selection): account connect/disconnect, an "enable publish" toggle (disabled until connected) driving `composerSlice.selectedPlatforms`, and the existing settings-panel stub below (all four stay "No settings yet.", including YouTube).
- Standalone Accounts screen and the Composer/Accounts tab switcher in `App.tsx` are removed; connect/disconnect logic moves into each platform tab.
- `PlatformSelector` (checkbox list) is deleted — its role is now each tab's own enable toggle.
- Right column: summary (video/title, enabled platforms + connected account name, scheduled time) → Publish/Schedule button (moved here) → always-visible status list, one row per enabled platform, in idle state before publish and live/final after.
- No persistence work, no real per-platform settings, no new dependencies, no changes to `settingsSlice`, no changes to adapter upload/publish logic.

## Implementation

### 1. Layout shell — `src/components/AppShell/`
New folder, following the existing per-component-folder + barrel convention (`VideoDropZone/`, `PlatformSelector/`, etc.):
- `AppTopBar.tsx`: MUI `AppBar` (`position="static"`, not `fixed` — sits in normal flow inside a flex column, avoids manual offset math) + `Toolbar`. Hardcoded `Typography` "Multiposter" left; version on the right from `getVersion()` (`@tauri-apps/api/app`, already a dependency) fetched once via `useEffect`.
- `AppShell.tsx`: props `{ left: ReactNode; center: ReactNode; right: ReactNode }`, purely presentational. Outer `Box` `display:flex; flexDirection:column; height:'100vh'; width:'100%'` (no need to touch global CSS — confirmed there is no `App.css`, and `index.html`/`main.tsx` have no root sizing to fight). Renders `<AppTopBar/>` then a row `Box` (`display:flex; flex:1; minHeight:0`) with three children at `flexBasis` 20% / 55% / 25%, `flexGrow:0` for the outer two, `flexGrow:1` for center, each `overflowY:auto`, side borders on left/right columns via `divider`.
- `index.ts` barrel exporting both.

### 2. `src/App.tsx` (rework)
Remove the `Tabs`/`useState` switcher and `AccountsSettings` import entirely. Becomes:
```tsx
<AppShell left={<HistoryPanel />} center={<ComposerScreen />} right={<SummaryPanel />} />
```

### 3. Left column — `src/features/history/HistoryPanel.tsx` (new feature folder + `index.ts`)
No props, no Redux. `Typography variant="h6"` "History" + `Typography variant="body2" color="text.secondary"` "No history yet." in a padded `Box`.

### 4. Shared account connector — `src/components/PlatformAccountConnector/PlatformAccountConnector.tsx` (+ `index.ts`)
Extracted from `AccountsSettings.tsx`'s `AccountRow` (`src/features/accounts/AccountsSettings.tsx:16-52`) as a reusable `{ platform: Platform }` component: same `selectAccountByPlatform`/`pendingPlatforms`/`errors` selectors, same `connectPlatform`/`disconnectPlatform` thunks, same avatar/name/error/Connect-or-Disconnect layout. No logic changes — pure relocation so it can be mounted per platform tab instead of only on a standalone screen.

### 5. Center column rework — `src/features/composer/`
- **`ComposerScreen.tsx`**: becomes a thin tab container. Local `useState<'common' | Platform>('common')`, header `Typography` ("New upload task"), MUI `Tabs`/`Tab` for `common, youtube, x, tiktok, instagram` in that order, then renders `<ComposerCommonTab/>` or `<PlatformTab platform={tab}/>`. Drops the Publish button, `publicationId` state, and `UploadProgressList` mount (moving to `SummaryPanel`), and drops the `<PlatformSelector/>`/`<PlatformSettingsTabs/>` mounts.
- **`ComposerCommonTab.tsx`** (new): everything from the current `ComposerScreen.tsx:52-116` body except the platform selector/settings/publish button — `VideoDropZone`, title/description fields, hashtag chip input (`hashtagInput` state + `commitHashtagInput`/`removeHashtag`, copied verbatim), and the `scheduleMode` radio group + `scheduledAt` field, copied verbatim. Use `Box sx={{ p: 3 }}` instead of the current centered `Container maxWidth="sm"` since this now lives in a ~55%-wide column, not a full page.
- **`PlatformTab.tsx`** (new): props `{ platform: Platform }`. Renders, top to bottom: `<PlatformAccountConnector platform={platform}/>`, then a `Switch`/`FormControlLabel` "Enable publish to this platform" (`checked={selectedPlatforms.includes(platform)}`, `disabled={!account}`, `onChange` dispatches `togglePlatform(platform)`), then the platform's existing settings panel via the `PLATFORM_PANELS` map (moved here from `PlatformSettingsTabs.tsx:18-23` — same four imports from `platforms/{youtube,x,instagram,tiktok}`).
- Update `src/features/composer/index.ts` to export `ComposerCommonTab`, `PlatformTab`, `SummaryPanel` alongside existing exports.

### 6. `UploadProgressList` rework — `src/components/UploadProgress/UploadProgressList.tsx`
Change props from `{ publicationId: string }` to `{ selectedPlatforms: Platform[]; publicationId?: string }`. When `publicationId` is set and present in `state.publications.items`, render its real `platforms` rows as today. Otherwise, synthesize one row per `selectedPlatforms` entry with `status: 'idle'`, `progress: 0`, `error: undefined` — `'idle'` is already a valid `PublicationStatus` and `UploadProgress` already renders it correctly (indeterminate bar). Since `createPublication` fires synchronously at the start of the `startPublication` thunk (`publicationsSlice.ts:28`), the switch from synthetic to real rows happens without a gap. No changes needed to `UploadProgress.tsx` itself.

### 7. Right column — `src/features/composer/SummaryPanel.tsx` (new)
No props. Local `publicationId` state + `publish()` function moved verbatim from the current `ComposerScreen.tsx:31-36`. Reads `composer.{video,title,scheduledAt,selectedPlatforms}` and, per selected platform, `selectAccountByPlatform` for display name. Renders: "Summary" header → video filename (+ thumbnail via `convertFileSrc(video.thumbnailPath)` guarded for the optional `thumbnailPath`, falling back to filename-only) → title → per-platform rows (label + connected account name) → scheduled time or "Publish immediately" → Publish/Schedule button (same `disabled={!video || selectedPlatforms.length===0}` guard) → `<UploadProgressList selectedPlatforms={selectedPlatforms} publicationId={publicationId}/>`.

### 8. Removals
- Delete `src/components/PlatformSelector/` (both files).
- Delete `src/components/PlatformSettingsTabs/` (its `PLATFORM_PANELS` map moves into `PlatformTab.tsx`, and its per-platform-tab responsibility is now owned by `ComposerScreen`'s own top-level Tabs — a second nested tab bar would be redundant).
- Delete `src/features/accounts/AccountsSettings.tsx`; update `src/features/accounts/index.ts` to drop its export (keep the slice exports, still used by `store/index.ts` and `PlatformAccountConnector`).
- Remove now-dead imports in `App.tsx` (`Tabs`/`Tab`/local tab state).

### 9. `tauri.conf.json`
No required change (resizability is already the Tauri default; no `App.css` conflicts exist). Optional, separately callable-out cosmetic fix: change `productName` and `windows[0].title` from `"scaffold"` to `"Multiposter"`.

## Verification

- `npx tsc --noEmit` — catches prop-shape mismatches (esp. new `UploadProgressList` call sites) and dangling imports from deleted files.
- `npm run lint` — catches unused imports left behind by the removals.
- `npm run tauri dev` — manually verify: 3-column layout fills the window and resizes correctly; AppBar shows name+version; each platform tab shows connect/disconnect + enable toggle (toggle disabled until connected) + stub settings; Common tab still works exactly as before (video drop, title/description/hashtags, now/schedule); Summary panel updates live as fields change; Publish button in Summary panel triggers the same `startPublication` flow and status list transitions from idle → uploading → completed/failed per platform; History panel shows its placeholder text.
- No automated UI test suite exists in this repo (confirmed — no test runner/config found), so manual verification via `tauri dev` is the only check beyond typecheck/lint.

## Notes for Implementer

- `VideoFile.thumbnailPath` is optional — guard the `<img>` in `SummaryPanel`.
- Three components (`AccountsSettings.tsx`, `PlatformSelector.tsx`, `PlatformSettingsTabs.tsx`) each currently duplicate an identical `PLATFORM_LABELS` map. Since two of those files are being deleted and one relocated, consider consolidating this into a single `src/domain/platform/labels.ts` constant used by `PlatformAccountConnector` and `PlatformTab` — optional cleanup, not required.
- Suggested order: layout shell + AppBar (verify with placeholder children first) → History placeholder → `PlatformAccountConnector` → center tabs rework (`ComposerCommonTab`, `PlatformTab`, slim `ComposerScreen`) → `UploadProgressList` rework → `SummaryPanel` → wire `App.tsx` → delete `PlatformSelector`/`PlatformSettingsTabs`/`AccountsSettings` and clean up barrels → typecheck/lint/manual run.
