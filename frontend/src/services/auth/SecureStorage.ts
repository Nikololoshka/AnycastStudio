import { invoke } from '@tauri-apps/api/core';

export function storeCredential(accountId: string, secret: string): Promise<void> {
  return invoke('store_credential', { accountId, secret });
}

export function getCredential(accountId: string): Promise<string> {
  return invoke('get_credential', { accountId });
}

export function deleteCredential(accountId: string): Promise<void> {
  return invoke('delete_credential', { accountId });
}
