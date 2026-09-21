import { invoke } from '@tauri-apps/api/core';

export interface OAuthCallbackParams {
  code?: string;
  state?: string;
  error?: string;
}

export function startOAuthCallbackServer(): Promise<number> {
  return invoke<number>('start_oauth_callback_server');
}

export function awaitOAuthCallback(timeoutSecs = 300): Promise<OAuthCallbackParams> {
  return invoke<OAuthCallbackParams>('await_oauth_callback', { timeoutSecs });
}

export function startFixedPortOAuthCallbackServer(port: number): Promise<number> {
  return invoke<number>('start_fixed_port_oauth_callback_server', { port });
}

export function cancelOAuthCallback(): Promise<void> {
  return invoke<void>('cancel_oauth_callback');
}
