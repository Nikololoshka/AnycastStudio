# Suppress harmless linker_messages warning in dev builds

## Context

Running `npm run tauri dev` shows a Cargo warning after compiling `scaffold_lib`:

```
warning: linker stdout: Создается библиотека ...scaffold_lib.dll.lib и объект ...scaffold_lib.dll.exp
  = note: `#[warn(linker_messages)]` on by default
warning: `scaffold` (lib) generated 1 warning
```

This is not an error — it's MSVC `link.exe` announcing it created the import
library (`.dll.lib`) and export file (`.dll.exp`) for the `cdylib`/`rlib`
target Tauri scaffolds by default. Recent Rust toolchains forward that
linker stdout as a `linker_messages` lint, so Cargo prints it as a build
warning even though nothing is wrong. The user confirmed the app runs fine
and just wants this cosmetic noise silenced.

## Change

Add a Cargo config that disables the `linker_messages` lint for the MSVC
target, scoped to `src-tauri` only (no `src-tauria/.cargo/config.toml`
exists yet).

Create `src-tauri/.cargo/config.toml`:

```toml
[target.x86_64-pc-windows-msvc]
rustflags = ["-Alinker_messages"]
```

This affects only the Rust/Cargo build inside `src-tauri`, not the
TypeScript/Vite side, and doesn't touch business logic, architecture, or
any sensitive area — purely a build-noise suppression.

## Verification

- Run `npm run tauri dev` again and confirm the `warning: linker stdout: ...`
  / `#[warn(linker_messages)]` lines no longer appear after
  `Compiling scaffold v0.1.0`.
- Confirm the app still builds and launches normally (`Finished dev profile`,
  window opens).
