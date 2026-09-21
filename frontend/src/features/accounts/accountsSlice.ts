import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { ConnectedAccount, Platform } from '../../domain/platform/types';
import type { RootState } from '../../app/store';
import { getAuthFor } from '../../platforms/auth';
import {
  loadPersistedAccounts,
  removePersistedAccount,
  savePersistedAccounts,
  upsertPersistedAccount,
} from '../../services/persistence';

export interface AccountsState {
  items: Record<string, ConnectedAccount>;
  pendingPlatforms: Platform[];
  disconnectingAccountIds: string[];
  errors: Partial<Record<Platform, string>>;
}

const initialState: AccountsState = {
  items: {},
  pendingPlatforms: [],
  disconnectingAccountIds: [],
  errors: {},
};

export const connectPlatform = createAsyncThunk<ConnectedAccount, Platform>(
  'accounts/connect',
  async (platform, { signal }) => {
    const account = await getAuthFor(platform).connect(signal);
    await upsertPersistedAccount(account);
    return account;
  },
);

export const disconnectPlatform = createAsyncThunk<string, string>(
  'accounts/disconnect',
  async (accountId, { getState }) => {
    const account = (getState() as RootState).accounts.items[accountId];
    if (!account) throw new Error(`no connected account with id ${accountId}`);
    await getAuthFor(account.platform).disconnect(accountId);
    await removePersistedAccount(accountId);
    return accountId;
  },
);

export const restoreAccounts = createAsyncThunk<{
  restored: ConnectedAccount[];
  failed: Platform[];
}>('accounts/restore', async () => {
  const persisted = await loadPersistedAccounts();
  const restored: ConnectedAccount[] = [];
  const failed: Platform[] = [];

  for (const account of persisted) {
    const auth = getAuthFor(account.platform);
    try {
      if (!auth.getValidAccessToken)
        throw new Error(`${account.platform} auth is not implemented yet`);
      await auth.getValidAccessToken(account.id);
      restored.push(account);
    } catch {
      failed.push(account.platform);
    }
  }

  if (restored.length !== persisted.length) {
    await savePersistedAccounts(restored);
  }

  return { restored, failed };
});

const accountsSlice = createSlice({
  name: 'accounts',
  initialState,
  reducers: {
    setAccount(state, action: PayloadAction<ConnectedAccount>) {
      state.items[action.payload.id] = action.payload;
    },
    removeAccount(state, action: PayloadAction<string>) {
      delete state.items[action.payload];
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(connectPlatform.pending, (state, action) => {
        state.pendingPlatforms.push(action.meta.arg);
        delete state.errors[action.meta.arg];
      })
      .addCase(connectPlatform.fulfilled, (state, action) => {
        state.pendingPlatforms = state.pendingPlatforms.filter(
          (platform) => platform !== action.meta.arg,
        );
        state.items[action.payload.id] = action.payload;
      })
      .addCase(connectPlatform.rejected, (state, action) => {
        state.pendingPlatforms = state.pendingPlatforms.filter(
          (platform) => platform !== action.meta.arg,
        );
        if (action.meta.aborted || action.error.name === 'ConnectCancelledError') return;
        state.errors[action.meta.arg] = action.error.message ?? 'connection failed';
      })
      .addCase(disconnectPlatform.pending, (state, action) => {
        state.disconnectingAccountIds.push(action.meta.arg);
      })
      .addCase(disconnectPlatform.fulfilled, (state, action) => {
        state.disconnectingAccountIds = state.disconnectingAccountIds.filter(
          (accountId) => accountId !== action.meta.arg,
        );
        delete state.items[action.payload];
      })
      .addCase(disconnectPlatform.rejected, (state, action) => {
        state.disconnectingAccountIds = state.disconnectingAccountIds.filter(
          (accountId) => accountId !== action.meta.arg,
        );
        const account = state.items[action.meta.arg];
        if (account) {
          state.errors[account.platform] = action.error.message ?? 'disconnect failed';
        }
      })
      .addCase(restoreAccounts.fulfilled, (state, action) => {
        for (const account of action.payload.restored) {
          state.items[account.id] = account;
        }
        for (const platform of action.payload.failed) {
          state.errors[platform] = 'session expired, please reconnect';
        }
      });
  },
});

export const { setAccount, removeAccount } = accountsSlice.actions;

export function selectIsDisconnecting(state: RootState, accountId: string): boolean {
  return state.accounts.disconnectingAccountIds.includes(accountId);
}

export function selectAccountByPlatform(
  state: RootState,
  platform: Platform,
): ConnectedAccount | undefined {
  return Object.values(state.accounts.items).find((account) => account.platform === platform);
}

export default accountsSlice.reducer;
