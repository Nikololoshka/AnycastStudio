import type { ConnectedAccount } from '../../domain/platform/types';
import { getPersisted, setPersisted } from './AppStore';

const CONNECTED_ACCOUNTS_KEY = 'connectedAccounts';

export async function loadPersistedAccounts(): Promise<ConnectedAccount[]> {
  return (await getPersisted<ConnectedAccount[]>(CONNECTED_ACCOUNTS_KEY)) ?? [];
}

export async function savePersistedAccounts(accounts: ConnectedAccount[]): Promise<void> {
  await setPersisted(CONNECTED_ACCOUNTS_KEY, accounts);
}

export async function upsertPersistedAccount(account: ConnectedAccount): Promise<void> {
  const accounts = await loadPersistedAccounts();
  const next = accounts.filter((existing) => existing.id !== account.id);
  next.push(account);
  await savePersistedAccounts(next);
}

export async function removePersistedAccount(accountId: string): Promise<void> {
  const accounts = await loadPersistedAccounts();
  await savePersistedAccounts(accounts.filter((account) => account.id !== accountId));
}
