# Multi-Platform Video Uploader

Windows desktop client (Tauri + Rust + React + TypeScript + HeroUI + Tailwind CSS + Redux Toolkit)
for publishing videos to YouTube, X, Instagram, and TikTok from one interface.

---

## Purpose

This file is the primary operating manual for AI agents working in this repository.

It should give the agent enough context to:

- understand what the project does;
- follow the correct architecture and conventions;
- place code in the right directories;
- run the right commands for setup and validation;
- avoid unsafe or low-quality changes;
- know when to stop and ask a human.

---

## Project Snapshot

- Project type: Windows desktop app (Tauri)
- Primary users: content creators publishing the same video to multiple platforms at once
- Domain: multi-platform social video publishing (YouTube, X, Instagram, TikTok)
- Maintainers: solo developer project
- Default branch: `master`

---

## Agent Principles

Unless the user explicitly asks otherwise, the agent should:

- prefer the smallest safe change that solves the task;
- preserve existing architecture and naming conventions;
- respect the dependency direction (see Architecture);
- verify work before finishing (typecheck, lint, run the app when relevant);
- avoid speculative refactors;
- ask before destructive, irreversible, or scope-expanding operations.

### Optimize For

1. Correctness
2. Maintainability
3. Speed

### Never Do These By Default

- Rewrite architecture without being asked.
- Introduce a new dependency when an existing project dependency can solve the problem.
- Put business logic in Rust — it belongs in TypeScript (see Architecture for the narrow upload-loop exception).
- Add comments explaining what code does (see Code Style).
- Guess around OAuth, token storage, or credential handling (see Security).

---

## Tech Stack

### Core Stack

- Language(s): TypeScript 6.0, Rust (edition 2021)
- Runtime(s): Node.js 24, Tauri 2
- Framework(s): React 19.1, Redux Toolkit 2.12
- Package manager(s): npm
- Build tool(s): Vite 8.0, tsc
- Database(s): none — no backend, no persistent DB
- Messaging / queueing: none
- Cache / storage: Tauri Store plugin (`tauri-plugin-store`) for app state, OS keyring (`keyring` crate) for secrets
- Hosting / infrastructure: none — local desktop app, no server component

### Key Libraries And Services

| Area              | Library / Service              | Version    | Purpose                                       | Notes / Constraints                                                                    |
| ----------------- | ------------------------------ | ---------- | --------------------------------------------- | -------------------------------------------------------------------------------------- |
| UI                | HeroUI (v3)                    | 3.2        | Component library                             | Compound components (`Card.Header`, `Tabs.Tab`); built on React Aria Components        |
| Styling           | Tailwind CSS                   | 4.3        | Utility styling, theme tokens                 | `@tailwindcss/vite`; theme variables overridden in `src/styles.css`                    |
| Icons             | `lucide-react`, `simple-icons` | 1.47 / 16  | UI icons, platform brand logos                | Brand logos only through `components/PlatformGlyph`                                    |
| Animation         | `motion`                       | 13.4       | Transitions and state changes                 | `MotionConfig reducedMotion="user"` set in `app/providers`                             |
| Dates             | `@internationalized/date`      | 3          | Date values for the HeroUI DatePicker         | Publication dates are stored as ISO strings in Redux                                   |
| State             | Redux Toolkit + react-redux    | 2.12 / 9.3 | App state, feature slices                     | One slice per feature under `src/features/*`                                           |
| i18n              | `i18next`, `react-i18next`     | 25 / 16    | English and Russian UI strings                | JSON resources in `src/locales/<lang>/<namespace>.json`; setup in `src/app/i18n`       |
| Desktop shell     | Tauri                          | 2          | Native window, filesystem, secure storage     | Rust stays thin — see Architecture                                                     |
| Auth              | keyring (Rust), PKCE (TS)      | 3          | OS-level credential storage + OAuth PKCE flow | YouTube OAuth uses a loopback HTTP server (`tiny_http`)                                |
| Dialogs           | `tauri-plugin-dialog`          | 2.7.3      | Native file picker                            | Used by `services/filesystem`                                                          |
| Networking (Rust) | `reqwest`                      | 0.12       | HTTP client for platform upload loops         | rustls-tls; used only by upload-loop Rust commands (e.g. YouTube), not general-purpose |

### Version Policy

- Version source of truth: `package.json` (JS/TS), `src-tauri/Cargo.toml` (Rust)
- Dependency update policy: manual

---

## Architecture

- Architecture style: layered, feature-oriented on the frontend; thin native shell on the backend
- High-level description: all business logic (composing a publication, adapting it per platform, uploading, auth) lives in TypeScript. Rust is limited to what only the OS can do: filesystem access, secure credential storage, native dialogs, the OAuth loopback listener.
- Main modules: `domain` (pure types/rules), `platforms` (per-platform adapters), `services` (upload, scheduler, filesystem, auth, persistence), `features` (Redux slices + screens), `app` (store/router/providers)
- Main data flow: React UI → Redux → Application Services → Platform Adapters → Platform APIs
- State management: Redux Toolkit, one slice per feature (`accountsSlice`, `composerSlice`, `publicationsSlice`, `settingsSlice`)
- Integration boundaries: YouTube Data API v3, X API, Instagram API, TikTok API — each behind its own adapter in `src/platforms/<platform>/`
- Hard constraints: business logic must not live in `src-tauri/`; a platform adapter must not be called directly from UI code, only through `services/upload`

### Architectural Rules

- Put business/domain logic in `src/domain` or `src/services`, not in `src-tauri/src/commands`.
  - **Exception**: a platform's network I/O-bound upload loop (chunking, retry/backoff, progress) may live in a Rust command when performance requires it. Everything else — auth/token handling, validation, publish/schedule REST calls, orchestration — stays in TypeScript. Don't use this exception to justify moving other business logic into Rust.
- Keep each `src/platforms/<platform>` adapter independent — no cross-platform imports between adapter folders.
- Every platform adapter implements `PlatformAdapter` (`src/platforms/PlatformAdapter.ts`).
- New Redux state goes in a feature slice under `src/features/<feature>`, not in a shared/global slice.
- UI components call services, never platform adapters or Tauri commands, directly.
- Build UI from HeroUI components before writing custom markup; style with Tailwind utilities, not inline `style` objects or CSS files per component.
- Colors, spacing and fonts come from the theme tokens (`bg-surface`, `text-muted`, `text-accent`, `font-display`, …). Add a new token to `src/styles.css` for both light and dark instead of hardcoding a hex value.
- Light and dark themes are driven by the `dark` class on `<html>`, set by `ThemeSync` in `app/providers` from `settings.theme`.
- UI text goes through `useTranslation` and the JSON resources in `src/locales/<lang>/`; never hardcode a user-visible string in a component. Keep the `en` and `ru` files in sync — the keys are typed from the `en` resources in `src/app/i18n/i18next.d.ts`.
- The active language lives in `settings.language`, is applied by `LanguageSync` in `app/providers` (i18next plus the React Aria `I18nProvider` that localises HeroUI dates and numbers), and is persisted through `services/persistence/AppSettingsStore`.

---

## Repository Structure

```text
src/
├─ app/           # store, router, top-level providers wiring
├─ domain/        # pure business types and rules (publication, platform, video) — no framework deps
├─ features/      # Redux slices + screens, one folder per feature (composer, accounts, publications, settings)
├─ platforms/     # one adapter per platform (youtube, x, instagram, tiktok), implementing PlatformAdapter
├─ services/      # application services: upload, scheduler, filesystem, auth, persistence
├─ components/    # shared reusable UI components (AppShell, PlatformGlyph, SettingSwitch, …)
├─ locales/       # translation resources, one folder per language (en, ru), one JSON per namespace
├─ styles.css     # Tailwind + HeroUI imports, light/dark theme tokens, scrollbar and font setup
└─ main.tsx

src-tauri/src/commands/   # Tauri command stubs (filesystem, oauth, secure_storage) — system-level only
```

### File Placement Rules

- New platform support goes in `src/platforms/<platform>/`, implementing `PlatformAdapter`.
- New screens/capabilities go in `src/features/<feature>/`, with their own slice and `index.ts`.
- Cross-feature reusable UI goes in `src/components/`.
- Cross-feature business rules with no UI go in `src/domain/`.
- Anything needing OS access (filesystem, secure storage, native dialogs, OAuth loopback) is a Rust command in `src-tauri/src/commands/`, called from a TypeScript service.

---

## Environment Setup

### Required Tooling

- Required tools: Node.js 24.x, npm, Rust toolchain (for Tauri), Windows
- Install dependencies: `npm install`
- Start local environment: `npm run tauri dev`
- Load environment variables from: `.env.local`

### Setup Notes

- YouTube OAuth needs a Google Cloud OAuth client (type: Desktop app, YouTube Data API v3 enabled). Set `VITE_YOUTUBE_CLIENT_ID` in `.env.local`.
- No local services (DB, Docker, queue) are required.

---

## Development Commands

| Task                 | Command             | Notes                                          |
| -------------------- | ------------------- | ---------------------------------------------- |
| Install dependencies | `npm install`       |                                                |
| Start development    | `npm run tauri dev` | Launches the Tauri desktop shell with Vite HMR |
| Start frontend only  | `npm run dev`       | Vite dev server, no native shell               |
| Build                | `npm run build`     | Runs `tsc` then `vite build`                   |
| Typecheck            | `npx tsc --noEmit`  |                                                |
| Lint                 | `npm run lint`      | ESLint (typescript-eslint + react-hooks)       |
| Format               | `npm run format`    | Prettier, writes in place                      |

---

## Code Style And Naming

- Formatter: Prettier (`.prettierrc.json`)
- Linter: ESLint (`eslint.config.js`) — typescript-eslint + `eslint-plugin-react-hooks`
- Type policy: strict (`tsconfig.json`: `strict`, `noUnusedLocals`, `noUnusedParameters`)
- Comments policy: write self-explanatory code instead of comments. Name things clearly, extract functions/variables to convey intent, and let types carry the shape of the data. Don't add comments explaining what code does — if code needs a comment to be understood, restructure it instead.
- Import policy: relative within a feature/module, no path aliases configured
- Styling: Tailwind utility classes in `className`; no CSS modules, no `style` props for anything a token or utility covers

### Style Do / Don't

Do:

- use names that reflect intent;
- keep each feature/platform folder cohesive and self-contained;
- follow the adapter pattern already used by existing platforms when adding a new one;
- reach for an existing HeroUI component (and its compound parts) before building one by hand.

Don't:

- add comments explaining what code does;
- put unrelated logic in a shared "utils" file;
- hardcode colors or reintroduce a second component library;
- call a platform adapter or Tauri command directly from UI code.

---

## Security And Safety Boundaries

Treat this section as mandatory.

### Hard Rules

- Never commit secrets, OAuth client secrets, access tokens, or `.env.local`.
- Never hardcode credentials in source, tests, or docs.
- OAuth tokens and platform credentials go through the OS keyring (`src-tauri/src/commands/secure_storage.rs`, `keyring` crate) — never plain files, never Redux state, never `localStorage`.
- Redact tokens and credentials from logs.

### Human Approval Required Before

- changing OAuth or credential-handling logic (`src/services/auth/*`, `src-tauri/src/commands/oauth.rs`, `src-tauri/src/commands/secure_storage.rs`);
- deleting user data or local files;
- installing or replacing major dependencies;
- rotating secrets or changing `.env.local` handling.

### Sensitive Areas

- Authentication / authorization: `src/services/auth/` (PKCE, loopback OAuth), `src-tauri/src/commands/oauth.rs`
- Credential storage: `src-tauri/src/commands/secure_storage.rs`, `src/services/auth/SecureStorage.ts`
- Configuration: `.env.local` (holds `VITE_YOUTUBE_CLIENT_ID`, never committed)

---

## Writing Code

Invoke the `caveman` skill before writing code. Keep narration around the change
ultra-compressed; the code itself still follows normal syntax and the Code Style rule above.

## Tools

- For bash commands - @.cluade/RTK.md

---

## Optional Cross-Tool Alignment

If this repository starts using other tool-specific AI instruction files
(`.github/copilot-instructions.md`, `.cursorrules`, `.aider.conf.yml`, `AGENTS.md`, etc.),
keep them aligned with this file. Prefer this file as the single authoritative source
and mirror only the minimum necessary into the others.

---

## Maintenance Checklist For Humans

- Update this file whenever the architecture, stack, commands, or workflow change.
- Keep commands executable exactly as written.
- Split this file into nested `CLAUDE.md` files if it grows too broad for one file.
