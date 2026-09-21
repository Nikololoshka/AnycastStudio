# Persist YouTube connection across app restarts

## Context

YouTube OAuth already requests and stores a refresh token in the OS keyring
(`YouTubeAuth.ts`), and `getValidAccessToken` correctly refreshes an expired
access token during a running session. But nothing survives a restart: the
list of connected accounts lives only in in-memory Redux state
(`accountsSlice.items`), and no code reads the keyring back on launch. So
today the user must redo the full OAuth consent flow every time they restart
the app, even though a valid refresh token is already sitting in the keyring.

Goal: connect once, stay connected across restarts, until the user explicitly
disconnects or Google revokes access.

## Approach

Keep tokens exactly where they are (OS keyring, unchanged). Add a small
**persisted index of which accounts are connected** (id/platform/displayName/
avatarUrl — no secrets) using the already-integrated `tauri-plugin-store`
wrapper (`src/services/persistence/AppStore.ts`), then rehydrate Redux from
that index at startup, validating/refreshing each token via the existing
`getValidAccessToken`.

### 1. Persist the account index

New file `src/services/persistence/AccountsStore.ts`:
- `loadPersistedAccounts(): Promise<ConnectedAccount[]>`
- `savePersistedAccounts(accounts: ConnectedAccount[]): Promise<void>`

Backed by `getPersisted`/`setPersisted` from `AppStore.ts` under a single key
(e.g. `'connectedAccounts'`), storing the `ConnectedAccount[]` array (no
tokens — those stay solely in the keyring via `SecureStorage`).

### 2. Keep the index in sync with connect/disconnect

In `src/features/accounts/accountsSlice.ts`:
- `connectPlatform` thunk: after `getAuthFor(platform).connect()` resolves,
  read the current persisted list, upsert the new account, save it back.
- `disconnectPlatform` thunk: after `getAuthFor(...).disconnect(accountId)`
  resolves, read the persisted list, remove the entry, save it back.

### 3. Add restore capability to `PlatformAuth`

`src/services/auth/PlatformAuth.ts`: add an optional method
`getValidAccessToken?(accountId: string): Promise<string>` to the interface.
`YouTubeAuth` already implements a method with this exact name/signature — no
change needed there. The stub `notImplemented` auth objects (x/instagram/
tiktok, in `src/platforms/auth.ts`) simply won't implement it, so restore
naturally skips platforms without real auth yet.

### 4. Restore thunk

In `accountsSlice.ts`, add `restoreAccounts` (`createAsyncThunk<void, void>`):
1. Load the persisted account list.
2. For each account, call `getAuthFor(account.platform).getValidAccessToken?.(account.id)`.
   - Success → dispatch `setAccount(account)`.
   - Throws / method missing → drop the account: remove it from the
     persisted list, and record a per-platform restore error (reuse
     `state.accounts.errors[platform]`, e.g. `"session expired, please reconnect"`)
     so `AccountsSettings.tsx` shows the existing error UI for that row
     without new UI work.
3. Save the pruned persisted list back (only accounts that verified).

### 5. Run it at startup

`src/app/providers/AppProviders.tsx`: add a `useEffect(() => { dispatch(restoreAccounts()); }, [])`
inside the existing `Provider` (via a small inner component with access to
`useDispatch`, matching how the store is already wired) — runs once when the
app mounts, before the user opens Accounts settings.

## Files touched

- `src/services/persistence/AccountsStore.ts` (new)
- `src/services/auth/PlatformAuth.ts` (add optional method to interface)
- `src/features/accounts/accountsSlice.ts` (persist on connect/disconnect, add `restoreAccounts` thunk)
- `src/app/providers/AppProviders.tsx` (dispatch `restoreAccounts` on mount)

No changes to `src-tauri/` (secure storage / OAuth loopback are untouched),
no changes to `YouTubeAuth.ts` itself, no new dependencies (`tauri-plugin-store`
is already integrated and wrapped).

## Verification

- `npx tsc --noEmit` and `npm run lint`.
- `npm run tauri dev`: connect YouTube, confirm channel shows connected in
  Accounts settings, fully quit the app (not just close window), relaunch,
  confirm the account still shows connected with no re-consent prompt.
- Simulate a revoked/invalid refresh token (e.g. manually corrupt the stored
  refresh token via Google Account's "Third-party access" revoke, or edit the
  keyring entry) and relaunch — confirm the account is dropped and the
  Accounts row shows an error/reconnect prompt instead of silently looking
  connected.
- Disconnect, relaunch, confirm it stays disconnected.
