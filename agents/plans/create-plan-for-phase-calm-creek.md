# Implementation Plan: Phase 4 — YouTube Adapter (validate → upload → publish)

## Context

The master build plan (`agents/plans/agents-prd-prd-md-fyi-create-implmeneta-binary-quilt.md`)
sequences the app into phases; Phases 0-3 are done (file services, composer UI,
capability model, and real working YouTube OAuth via `YouTubeAuth.ts`). Phase 4
is the first phase that actually moves bytes to a platform: it turns the
`YouTubeAdapter` stub into a real implementation and builds the orchestration
service (`UploadManager`) and Redux wiring that Phases 5-8 (parallel
publishing, retry, the other three platforms, scheduling, history) will all
build on top of. Getting this phase's shapes right — the adapter interface,
how progress flows to Redux, how a video id crosses from `upload()` into
`publish()`/`schedule()` — matters because four more adapters and a
multi-platform orchestrator get layered on top of whatever is decided here.

Current state relevant to this phase (verified by reading the files directly):

- `src/services/filesystem/FileReader.ts` — `TauriFileReader` (`size()`,
  `read(offset, size)`) is done and chunk-reads via real Rust commands.
- `src/platforms/youtube/YouTubeAuth.ts` — real PKCE OAuth, with
  `getValidAccessToken(accountId): Promise<string>` (handles refresh) ready to
  use.
- `src/features/accounts/accountsSlice.ts` — `selectAccountByPlatform` gives
  the connected YouTube `ConnectedAccount.id`.
- `src/platforms/youtube/YouTubeAdapter.ts` — `getCapabilities()` is correct
  and complete; `validate/upload/publish/schedule` all `throw new
Error("not implemented")`.
- `src/platforms/PlatformAdapter.ts` — interface + result types exist but are
  too thin: methods take a bare `PlatformPublication` (no video/title/
  description/hashtags/scheduledAt — those live on the parent `Publication`),
  and `UploadResult` has no field to carry the created YouTube video id
  forward into `publish()`/`schedule()`.
- `src/services/upload/index.ts` and `src/services/scheduler/index.ts` are
  both empty (`export {}`) — no `UploadManager` exists.
- `src/features/publications/publicationsSlice.ts` — state shape only
  (`PublicationTask = Publication`), zero reducers/thunks.
- `src/components/UploadProgress/UploadProgress.tsx` — a presentational stub
  (`{ platform, percent }` → MUI `LinearProgress`, already handles
  indeterminate when `percent` is undefined) with no data wired to it.
- All HTTP happens via plain `fetch` from TS (CSP disabled in
  `tauri.conf.json`, no Rust HTTP layer) — `YouTubeAuth.ts` already
  establishes this pattern; Phase 4 follows it, no new Rust needed.
- No test runner configured anywhere in the repo (no vitest/jest, no test
  files).

---

## 1. Widen the adapter contract (`src/platforms/PlatformAdapter.ts`)

Add a composed context type instead of touching `src/domain/publication/types.ts`
(that file is correct/complete per the PRD and shouldn't gain adapter-specific
plumbing fields):

```ts
export interface AdapterPublication extends PlatformPublication {
  accountId: string;
  video: VideoFile;
  title: string;
  description: string;
  hashtags: string[];
  scheduledAt?: string;
  uploadedVideoId?: string; // set by UploadManager between upload() and publish()/schedule()
}

export type UploadProgressCallback = (progress: {
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
}) => void;
```

Extend the result types to carry what the lifecycle needs:

```ts
export interface UploadResult {
  success: boolean;
  videoId?: string;
  error?: PublicationError;
}
export interface PublishResult {
  success: boolean;
  publishedUrl?: string;
  error?: PublicationError;
}
export interface ScheduleResult {
  success: boolean;
  scheduledAt: string;
  error?: PublicationError;
}
```

Update `PlatformAdapter` method signatures to take `AdapterPublication`, and
`upload` to take the progress callback:

```ts
upload(publication: AdapterPublication, onProgress: UploadProgressCallback): Promise<UploadResult>;
```

This is a deliberate, scoped deviation from the PRD's illustrative interface
snippet — worth a one-line note in the commit message. Update the other three
adapter stubs' (`XAdapter`, `InstagramAdapter`, `TikTokAdapter`) method
signatures to match mechanically; they keep throwing `not implemented`.

Progress is a plain callback (not an async generator or event emitter) to
match the codebase's existing minimal-dependency style (plain `fetch`, plain
classes, no event bus) — `UploadManager` translates each call into a Redux
dispatch.

---

## 2. `YouTubeAdapter.validate()`

Pure, synchronous, in `src/platforms/youtube/YouTubeAdapter.ts`:

- Required non-empty `title`.
- `video.size` against `getCapabilities().maxFileSize`.
- `video.mimeType` against `getCapabilities().supportedMimeTypes`.
- No duration check (no probing capability exists yet — don't invent one).

Returns `{ valid, errors }` via `ValidationResult`.

---

## 3. `YouTubeAdapter.upload()` — resumable upload

New helper module `src/platforms/youtube/resumableUpload.ts` (mirrors how
`YouTubeAuth.ts` factors token exchange into standalone functions), wired into
`YouTubeAdapter.upload()`.

**Initiate session:**

```
POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status
Authorization: Bearer <accessToken>
Content-Type: application/json; charset=UTF-8
X-Upload-Content-Type: <video.mimeType>
X-Upload-Content-Length: <video.size>

{ snippet: { title, description, tags: hashtags },
  status: { privacyStatus: "private"|"public"|"unlisted", selfDeclaredMadeForKids: false } }
```

Read the `Location` response header on `200` → resumable session URI.
`privacyStatus` read from `publication.settings` (check the exact key
`YouTubeSettingsPanel.tsx` uses before inventing one; default `"private"`).

**Chunk loop**, reading chunks via `TauriFileReader.read(offset, size)` (never
load the whole file into memory), chunk size `8 * 1024 * 1024` (multiple of
256 KiB per Google's protocol; balances IPC-serialization cost against
request count):

```
PUT <sessionUri>
Content-Length: <chunkSize>
Content-Range: bytes <offset>-<offset+chunkSize-1>/<totalSize>
```

- `308` → inspect `Range` response header, continue from the confirmed offset.
- `200`/`201` → final chunk; parse response body `Video.id` → `UploadResult.videoId`.
- `401` mid-loop → refresh once via `getValidAccessToken` and retry that one
  chunk (cheap since the method already exists); anything else 4xx → fail
  fast, no retry (retry policy is Phase 5 scope).
- Network failure → propagate as `PublicationError{type:"network"}`.
- After each accepted chunk, call `onProgress({ uploadedBytes, totalBytes, percent })`.

Token obtained once up front via `YouTubeAuth.getValidAccessToken(accountId)`.

---

## 4. `YouTubeAdapter.publish()` / `.schedule()`

Both are thin `videos.update` calls using `publication.uploadedVideoId`
(populated by `UploadManager`, see §6):

```
PUT https://www.googleapis.com/youtube/v3/videos?part=status
{ id: videoId, status: { privacyStatus, publishAt? } }
```

- `publish()`: `privacyStatus: "public"` (or the user's chosen setting),
  returns `{ success: true, publishedUrl: "https://youtu.be/<videoId>" }`.
- `schedule()`: `privacyStatus: "private"`, `publishAt: publication.scheduledAt`
  (YouTube requires private until `publishAt`), returns
  `{ success: true, scheduledAt: publication.scheduledAt }`.

---

## 5. `UploadManager` (new: `src/services/upload/UploadManager.ts`)

A single-platform sequencer — Phase 5 adds the multi-platform
`Promise.allSettled` fan-out on top, so design this as a plain async function
with no shared mutable state, ready to accept an `AbortSignal` later without a
rewrite.

```ts
export async function runPublicationTask(
  publication: Publication,
  platform: Platform,
  deps: {
    dispatch: AppDispatch;
    getAdapter: (p: Platform) => PlatformAdapter;
    getAccountId: (p: Platform) => string;
  },
): Promise<void>;
```

Sequence: build `AdapterPublication` from `publication` + its matching
`PlatformPublication` + resolved `accountId` → dispatch `status: "validating"`
→ `adapter.validate()` (fail → dispatch error, return) → dispatch
`"uploading"` → `adapter.upload(ctx, onProgress)` dispatching
`setPlatformProgress` per callback → on success, attach `uploadedVideoId` →
branch on `publication.scheduledAt` to `adapter.schedule()` vs
`adapter.publish()` → dispatch `"scheduled"` or `setPlatformCompleted`. Any
thrown error anywhere in the chain → `toPublicationError(error)` → dispatch
`setPlatformError`.

`toPublicationError(error: unknown): PublicationError` — small pure helper in
`src/services/upload/errors.ts`, maps to the existing `ErrorType` union
(default `"unknown"`).

Add `getAdapterFor(platform): PlatformAdapter` to `src/platforms/capabilities.ts`
(it already holds the adapters map internally).

Optionally also ship a thin fan-out (`runPublication(publication, platforms, deps)`
doing `Promise.allSettled` over `runPublicationTask` per enabled platform) —
PRD §18 describes exactly this shape and it costs nothing extra now, but it's
not required scope for Phase 4 to be complete.

---

## 6. `publicationsSlice` reducers + `startPublication` thunk

File: `src/features/publications/publicationsSlice.ts`. Add sync reducers:
`createPublication`, `setPlatformStatus`, `setPlatformProgress`,
`setPlatformError`, `setPlatformCompleted` — each looks up the matching entry
in `state.items[id].platforms` and mutates it (Immer). Matches the plain
`createSlice` reducer style already used in `composerSlice`.

Add `startPublication` as a `createAsyncThunk` (consistent with
`accountsSlice`'s existing `connectPlatform`/`disconnectPlatform` thunks):
builds a `Publication` from current composer state (new pure helper
`src/domain/publication/buildPublication.ts`), dispatches `createPublication`,
then runs `runPublicationTask` per enabled platform via `Promise.allSettled`,
resolving `getAccountId` through `selectAccountByPlatform` (throw if no
connected account).

Wire the Composer's Publish button (`src/features/composer/ComposerScreen.tsx`,
currently non-functional/disabled) to `dispatch(startPublication())` — this is
required to reach the phase's own verification target.

---

## 7. `UploadProgress` component wiring

`src/components/UploadProgress/UploadProgress.tsx` already renders
`{ platform, percent }` correctly (indeterminate when `percent` is
undefined) — extend props with `status: PublicationStatus` and
`error?: PublicationError` for status text / error display.

Add `src/components/UploadProgress/UploadProgressList.tsx`: a connected
component that selects `state.publications.items[publicationId]?.platforms`
and renders one `UploadProgress` per entry (mirrors the row/list split already
used by `PlatformSelector`). Mount it in `ComposerScreen.tsx` below the
Publish button, tracked via local `useState<string>()` set to the id returned
by the `startPublication` thunk.

---

## 8. Rust changes

None. `get_file_metadata`/`read_file_chunk` already cover everything
`validate()`/`upload()` need; no new Tauri command, so
`src-tauri/src/lib.rs`'s `invoke_handler` allowlist is untouched.

---

## 9. Optional: minimal vitest setup

No test runner exists in the repo today. `validate()`, `toPublicationError()`,
and the chunk/Content-Range parsing logic in `resumableUpload.ts` are pure
functions worth locking down before Phase 5's retry logic builds on them.
If time allows: `npm i -D vitest`, a `test` block added to the existing Vite
config, `"test": "vitest run"` in `package.json`, and three small test files
(`YouTubeAdapter.test.ts`, `errors.test.ts`, `resumableUpload.test.ts` with
`fetch`/`FileReader` mocked). This is explicitly optional — skip if
time-constrained and revisit later; do not attempt to test the full chunk
loop against real `fetch`/Tauri IPC, that's what manual verification is for.

---

## Suggested commit order

1. `PlatformAdapter.ts` — `AdapterPublication`, extended result types,
   `UploadProgressCallback`, updated interface signatures.
2. Update the four adapter stubs' signatures (mechanical); add
   `getAdapterFor()` to `platforms/capabilities.ts`.
3. `YouTubeAdapter.validate()`.
4. `resumableUpload.ts` + `YouTubeAdapter.upload()`.
5. `YouTubeAdapter.publish()` / `.schedule()`.
6. `services/upload/errors.ts` + `services/upload/UploadManager.ts`.
7. `publicationsSlice.ts` reducers + `startPublication` thunk +
   `domain/publication/buildPublication.ts`.
8. Wire `ComposerScreen.tsx` Publish button; extend `UploadProgress.tsx`
   props; add `UploadProgressList.tsx`; mount it.
9. (Optional) vitest setup + the three pure-logic test files.

## Verification

Connect a real YouTube account (Phase 3 OAuth) → drag in a short real test
video → fill title/description/hashtags → click Publish (publish-now, no
schedule) → confirm the `UploadProgressList` shows live percent during the
chunked upload and a completed/success state afterward → confirm the video
actually appears on the connected YouTube channel with the correct title,
description, and tags (hashtags → `snippet.tags`). Separately, set a future
`scheduledAt` and confirm the video is created as `private` with the correct
`publishAt` via the YouTube Studio UI or a `videos.list` check.

### Critical files

- `src/platforms/PlatformAdapter.ts`
- `src/platforms/youtube/YouTubeAdapter.ts` (+ new `resumableUpload.ts`)
- `src/services/upload/UploadManager.ts` (new, + `errors.ts`)
- `src/features/publications/publicationsSlice.ts`
- `src/domain/publication/buildPublication.ts` (new)
- `src/components/UploadProgress/UploadProgress.tsx` (+ new `UploadProgressList.tsx`)
- `src/features/composer/ComposerScreen.tsx`
