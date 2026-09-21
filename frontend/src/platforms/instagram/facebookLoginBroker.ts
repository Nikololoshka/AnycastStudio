import { openUrl } from '@tauri-apps/plugin-opener';
import { fetch } from '@tauri-apps/plugin-http';

const BROKER_BASE = 'https://nikololoshka-fileserver.online/multiposter/auth_facebook';
const START_TIMEOUT_MS = 10_000;
const POLL_TIMEOUT_MS = 40_000;
const RATE_LIMIT_BACKOFF_MS = 5_000;
const SERVER_ERROR_BACKOFF_MS = 5_000;
const CLIENT_TOKEN = import.meta.env.VITE_FACEBOOK_BROKER_TOKEN;

interface StartResponse {
  status: 'ok';
  auth_url: string;
  poll_token: string;
  expires_in: number;
}

type PollResponse =
  | { status: 'pending' }
  | { status: 'rate_limited' }
  | { status: 'server_error' }
  | {
      status: 'done';
      access_token: string;
      token_type: string;
      expires_in: number | null;
    }
  | { status: 'error'; error: string; error_reason?: string; message?: string }
  | { status: 'unauthorized' | 'not_found' | 'expired' | 'method_not_allowed' };

export interface FacebookUserToken {
  accessToken: string;
  expiresIn: number | null;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isTimeout(error: unknown): boolean {
  return (
    error instanceof DOMException && (error.name === 'TimeoutError' || error.name === 'AbortError')
  );
}

function timeoutSignal(ms: number, signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(ms);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}

async function startSession(signal?: AbortSignal): Promise<StartResponse> {
  if (!CLIENT_TOKEN) {
    throw new Error('VITE_FACEBOOK_BROKER_TOKEN is not configured');
  }

  const response = await fetch(`${BROKER_BASE}/start`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${CLIENT_TOKEN}` },
    signal: timeoutSignal(START_TIMEOUT_MS, signal),
  });
  if (response.status === 401) {
    throw new Error('Facebook sign-in was rejected: the app client token is invalid');
  }
  if (response.status === 429) {
    throw new Error('Facebook sign-in is rate limited, try again in a minute');
  }
  if (!response.ok) {
    throw new Error(`Facebook sign-in could not start: HTTP ${response.status}`);
  }

  const session: StartResponse = await response.json();
  if (session.status !== 'ok') {
    throw new Error(`Facebook sign-in could not start: ${session.status}`);
  }
  return session;
}

async function pollOnce(pollToken: string, signal?: AbortSignal): Promise<PollResponse> {
  const response = await fetch(`${BROKER_BASE}/poll`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${pollToken}` },
    signal: timeoutSignal(POLL_TIMEOUT_MS, signal),
  });
  try {
    return await response.json();
  } catch {
    throw new Error(`Facebook sign-in poll failed: HTTP ${response.status}`);
  }
}

function describeError(result: Extract<PollResponse, { status: 'error' }>): string {
  return result.message ?? result.error_reason ?? result.error;
}

async function awaitResult(
  pollToken: string,
  deadline: number,
  throwIfCancelled: () => void,
  signal?: AbortSignal,
): Promise<FacebookUserToken> {
  while (Date.now() < deadline) {
    throwIfCancelled();
    let result: PollResponse;
    try {
      result = await pollOnce(pollToken, signal);
    } catch (error) {
      throwIfCancelled();
      if (isTimeout(error)) continue;
      throw error;
    }

    switch (result.status) {
      case 'pending':
        continue;
      case 'rate_limited':
        await sleep(RATE_LIMIT_BACKOFF_MS);
        continue;
      case 'server_error':
        await sleep(SERVER_ERROR_BACKOFF_MS);
        continue;
      case 'done':
        return { accessToken: result.access_token, expiresIn: result.expires_in };
      case 'error':
        throw new Error(`Facebook sign-in was not completed: ${describeError(result)}`);
      default:
        throw new Error(`Facebook sign-in failed: ${result.status}`);
    }
  }
  throw new Error('Facebook sign-in timed out, please try again');
}

export async function signInWithFacebook(
  throwIfCancelled: () => void,
  signal?: AbortSignal,
): Promise<FacebookUserToken> {
  const session = await startSession(signal);
  const deadline = Date.now() + session.expires_in * 1000;
  throwIfCancelled();
  await openUrl(session.auth_url);
  return awaitResult(session.poll_token, deadline, throwIfCancelled, signal);
}
