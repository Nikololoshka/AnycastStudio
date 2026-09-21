# Base Project Structure — Multi-Platform Video Uploader

## Context

Repo has only the PRD (`agents/prd/PRD.md`) and `.claude/` config — no app code yet. This plan scaffolds the base project per the PRD's tech stack (Tauri + Rust + React + TypeScript + MUI + Redux Toolkit) and folder layout (PRD §21, §16, §42), so feature work can start directly against a working, buildable skeleton instead of an empty repo. Scope is structure only: empty/stub screens, wired-up store, adapter interfaces as types — no real upload/auth/platform logic.

## Approach

Use `create-tauri-app` (npm) with the React-TS template as the base, then layer PRD's architecture on top.

### 1. Scaffold Tauri + React + TS

- Run `npm create tauri-app@latest` into repo root (or a subfolder if the tool won't init into a non-empty dir — check first, since `.claude/`, `agents/`, `.git/` already exist; use `--force`/manual merge if needed) with template `react-ts`, package manager `npm`.
- Verify `npm run tauri dev` builds (Rust toolchain must be present — check with `cargo --version`; note in plan output if missing, don't install silently).

### 2. Add core dependencies

```
npm install @reduxjs/toolkit react-redux @mui/material @mui/icons-material @emotion/react @emotion/styled
```

### 3. Frontend folder structure (PRD §21)

Create under `src/` with minimal placeholder files (index barrel + a comment referencing its PRD section) so structure exists and imports resolve, but no logic:

```
src/
├── app/{store,router,providers}/     # store/index.ts sets up configureStore (empty reducer map)
├── domain/{publication,platform,video}/   # type-only modules: VideoFile, Publication, PlatformPublication, Platform, PublicationStatus (PRD §14-15)
├── features/{composer,accounts,publications,settings}/   # empty Redux slices co-located with placeholder components
├── platforms/{youtube,x,instagram,tiktok}/   # each exports a stub adapter implementing PlatformAdapter (PRD §16), throwing "not implemented"
├── services/{upload,scheduler,filesystem,auth}/   # interface stubs: FileReader (§23), PlatformAuth (§25)
├── components/{VideoDropZone,PlatformSelector,UploadProgress}/   # empty MUI component shells
└── main.tsx   # wraps App in ReduxProvider + MUI ThemeProvider
```

Shared domain types (PRD §13, §14, §15) go in `domain/platform/types.ts` and `domain/video/types.ts` / `domain/publication/types.ts`, copied verbatim from the PRD's TypeScript interfaces (`PlatformCapabilities`, `VideoFile`, `Publication`, `PlatformPublication`, `Platform`, `PublicationStatus`).

`PlatformAdapter` interface (PRD §16) goes in `platforms/PlatformAdapter.ts`; each of the four platform folders exports a class stub implementing it.

### 4. Redux store wiring

- `app/store/index.ts`: `configureStore` combining reducers from `features/*` (composer, accounts, publications, settings) per `AppState` shape (PRD §20).
- Each `features/*/slice.ts`: minimal `createSlice` with the state shape from PRD §20 (`ComposerState`, `PublicationsState`) and no-op reducers, or empty state for accounts/settings.
- `main.tsx` / `App.tsx`: wrap in `<Provider store={store}>` and MUI `<ThemeProvider>` + `<CssBaseline>`.

### 5. Rust side (`src-tauri/`)

- Keep the scaffolded default `src-tauri` from create-tauri-app as-is.
- Add empty module stubs matching PRD §22 responsibilities (`src-tauri/src/commands/` with `filesystem.rs`, `secure_storage.rs` placeholders exposing one stub `#[tauri::command]` each, e.g. `get_file_metadata`), registered in `main.rs`/`lib.rs`. No real implementation — just proves the Rust↔frontend command bridge compiles and is callable.

### 6. Root housekeeping

- `.gitignore` covering `node_modules/`, `src-tauri/target/`, `dist/`.
- Top-level `README.md` linking to the PRD and noting stack/run commands (`npm run tauri dev`).

## Files/Areas Touched

- Repo root: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `.gitignore`, `README.md` (new, from template)
- `src-tauri/`: default Tauri scaffold + `src/commands/*.rs` stubs
- `src/`: full structure above (new)

## Verification

1. `npm install` succeeds.
2. `npm run tauri dev` launches the app window without errors (blank/placeholder UI is fine).
3. `npx tsc --noEmit` passes (domain types and stub adapters type-check).
4. Confirm each `platforms/*` stub compiles against `PlatformAdapter` interface.
5. Confirm Redux DevTools shows the four `AppState` slices with expected initial shape.
