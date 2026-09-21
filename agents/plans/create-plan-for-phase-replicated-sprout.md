# Implementation Plan: Phase 1 — Video Input & Composer UI

## Context

Phase 0 (foundations) is already implemented and committed (`51fdf37 Added phase 0`):
domain types, the wired Redux store, `TauriFileReader` + Rust
`get_file_metadata`/`read_file_chunk`, `tauri-plugin-store`-backed persistence,
and `keyring`-backed secure storage are all in place and registered.

The next increment from `agents/plans/agents-prd-prd-md-fyi-create-implmeneta-binary-quilt.md`
is **Phase 1**: make the composer screen actually work end-to-end for video
input, with no platform/auth/upload logic yet. Today `ComposerScreen.tsx`,
`VideoDropZone`, and `PlatformSelector` are static MUI shells with no state,
and `composerSlice`/`settingsSlice`/`accountsSlice` all have empty `reducers: {}`.
This phase wires real drag-and-drop/file-picker input, populates `composer`
Redux state, and builds out the rest of the composer form (title/description/
hashtags/schedule radio) per PRD §6–§8, so a user can load a video and see its
metadata/thumbnail and fill in publication details — still with no platforms
wired up.

---

## 1. `composerSlice` actions

File: `src/features/composer/composerSlice.ts` (currently `reducers: {}`).

Add, using `createSlice`'s `PayloadAction`:

- `setVideo(video: VideoFile)`, `clearVideo()`
- `setTitle(title: string)`, `setDescription(description: string)`
- `setHashtags(hashtags: string[])`
- `setScheduledAt(scheduledAt: string | undefined)`
- `togglePlatform(platform: Platform)` — add/remove from `selectedPlatforms`
- `setPlatformSettings({ platform, settings }: { platform: Platform; settings: PlatformSettings })`
  — merges into `platformSettings[platform]`

Export the action creators alongside the existing default reducer export
(`src/features/composer/index.ts` currently just re-exports the reducer —
extend it to re-export the actions too, matching how other slices are wired).

## 2. Hashtag normalization util

New file: `src/domain/publication/normalizeHashtags.ts`, exported via the
existing `src/domain/publication/index.ts` barrel (`export * from "./types"`
pattern — add `export * from "./normalizeHashtags"`).

Per PRD §8: `"#video #technology #tutorial"` and `"video, technology, tutorial"`
must normalize to the same `string[]` (e.g. `["video", "technology", "tutorial"]`).
Implementation: split on whitespace and/or commas, strip a leading `#`,
lowercase, drop empties, dedupe — keep it a pure function so it's directly
unit-testable in isolation (no test runner is configured in the repo yet;
note this as a gap rather than silently adding one — flag for the user if a
test framework should be introduced now or deferred).

## 3. `VideoDropZone`: real file input

File: `src/components/VideoDropZone/VideoDropZone.tsx` (currently a static
`Box` with no handlers).

- Add `@tauri-apps/plugin-dialog` (`npm` package + Rust `tauri-plugin-dialog`
  crate + `.plugin(tauri_plugin_dialog::init())` in `src-tauri/src/lib.rs`,
  same registration pattern as `tauri_plugin_store`/`tauri_plugin_opener`) for
  the native "Choose File" picker — it is not yet a dependency in either
  `package.json` or `Cargo.toml`.
- Implement HTML5 drag-and-drop (`onDrop`/`onDragOver`) to accept a file path.
  Tauri's webview drop event gives a path directly (`webview://drag-drop` /
  `getCurrentWebview().onDragDropEvent` from `@tauri-apps/api/webview`) —
  use that rather than the browser `File` object, since Rust needs a path for
  `get_file_metadata`/`read_file_chunk`.
- On file selection (drop or picker), call `getFileMetadata` (already in
  `src/services/filesystem/FileReader.ts`) to get `size`/`mimeType`, build a
  `VideoFile` (id via `crypto.randomUUID()`, `path`, `name` from the path,
  `size`, `mimeType`), and dispatch `setVideo`.
- Thumbnail: default to the webview `<video>` canvas-capture approach per the
  plan's guidance (seek to ~1s, draw to an offscreen `<canvas>`, `toDataURL()`)
  rather than a Rust/ffmpeg sidecar, to keep Rust thin (PRD §22 intent). Store
  the resulting data URL directly on `VideoFile.thumbnailPath` (the field
  already exists in `src/domain/video/types.ts`) rather than adding a new field.
- Duration/resolution (`width`/`height`, `duration` fields already on
  `VideoFile`): read via the same `<video>` element's `loadedmetadata` event
  before capturing the thumbnail frame — no new Rust command needed for this
  in Phase 1.
- Render selected-state UI (thumbnail, name, formatted size/resolution/
  duration per PRD §7 example) plus remove/replace actions that dispatch
  `clearVideo` / re-open the picker.
- Read `composer.video` via `useSelector` to switch between empty-state and
  selected-state rendering.

## 4. `PlatformSelector`: drive from state, not hardcoded

File: `src/components/PlatformSelector/PlatformSelector.tsx` (currently a
static disabled checkbox list).

Phase 1 scope is only to make the checkboxes live against
`composer.selectedPlatforms` (dispatch `togglePlatform` on change) — real
`accountsSlice`/capability-driven connection status and disabling
unconnected/unsupported platforms is Phase 2/3 work per the plan and should
not be pulled forward here. Keep the platform list local for now; Phase 2
replaces it with capability-driven data.

## 5. `ComposerScreen.tsx` — full form layout

File: `src/features/composer/ComposerScreen.tsx` (currently just title +
`VideoDropZone` + `PlatformSelector`).

Add, per the PRD §6 mockup, each bound to `composer` state via
`useSelector`/`useDispatch`:

- Title `TextField` → `setTitle`
- Description multiline `TextField` → `setDescription`
- Hashtags input (free-text field that normalizes on blur/enter via
  `normalizeHashtags`, rendered back as chips — MUI `Chip` + a plain
  `TextField`, no new dependency needed) → `setHashtags`
- Publish-now / Schedule `RadioGroup`; selecting "Schedule" reveals a
  date/time input wired to `setScheduledAt` (full timezone-aware picker is
  Phase 7 — a plain `datetime-local` input is enough for now, stored as-is;
  don't build the UTC-conversion logic yet)
- A `Publish` `Button`, disabled for now (no publish pipeline exists before
  Phase 4/5) — wire it later, just place it per the mockup.

Keep the file focused on composition/layout; leave field-level validation
(PRD §26) to Phase 8 as the existing plan specifies.

---

## Verification

- `npm run tauri dev`: drag a real `.mp4` onto the drop zone and via
  "Choose File"; confirm thumbnail, name, formatted size/resolution/duration
  render, and Redux DevTools shows `composer.video` populated correctly.
- Type in title/description/hashtags, confirm normalized hashtag chips match
  for both `"#a #b"` and `"a, b"` input styles.
- Toggle platform checkboxes, confirm `composer.selectedPlatforms` updates.
- Remove/replace the video, confirm state clears/resets correctly.
- No test runner exists yet — if `normalizeHashtags` should get automated
  unit tests, flag that a test framework (e.g. Vitest, already compatible
  with the Vite setup) needs to be added; otherwise rely on manual/DevTools
  verification for this phase as the plan's own verification sections do
  throughout.
