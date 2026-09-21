import { cancelOAuthCallback } from './oauthLoopback';

export class ConnectCancelledError extends Error {
  constructor(platformLabel: string) {
    super(`${platformLabel} sign-in was cancelled`);
    this.name = 'ConnectCancelledError';
  }
}

export function isConnectCancelled(error: unknown): boolean {
  return (
    error instanceof ConnectCancelledError || (error as Error | undefined)?.name === 'AbortError'
  );
}

export async function withOAuthCancellation<T>(
  platformLabel: string,
  signal: AbortSignal | undefined,
  run: (throwIfCancelled: () => void) => Promise<T>,
): Promise<T> {
  const throwIfCancelled = () => {
    if (signal?.aborted) throw new ConnectCancelledError(platformLabel);
  };
  const stopLoopbackWait = () => {
    void cancelOAuthCallback();
  };

  throwIfCancelled();
  signal?.addEventListener('abort', stopLoopbackWait);
  try {
    return await run(throwIfCancelled);
  } catch (error) {
    if (signal?.aborted) throw new ConnectCancelledError(platformLabel);
    throw error;
  } finally {
    signal?.removeEventListener('abort', stopLoopbackWait);
  }
}
