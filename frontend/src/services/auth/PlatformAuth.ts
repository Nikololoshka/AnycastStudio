import type { ConnectedAccount } from '../../domain/platform/types';

export interface PlatformAuth {
  connect(signal?: AbortSignal): Promise<ConnectedAccount>;

  disconnect(accountId: string): Promise<void>;

  getAccount(): Promise<ConnectedAccount>;

  getValidAccessToken?(accountId: string): Promise<string>;
}
