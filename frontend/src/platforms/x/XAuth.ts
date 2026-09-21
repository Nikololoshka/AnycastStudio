import { openUrl } from '@tauri-apps/plugin-opener';
import { fetch } from '@tauri-apps/plugin-http';
import type { PlatformAuth } from '../../services/auth/PlatformAuth';
import {
  deleteCredential,
  getCredential,
  storeCredential,
} from '../../services/auth/SecureStorage';
import { generateCodeChallenge, generateCodeVerifier } from '../../services/auth/pkce';
import { withOAuthCancellation } from '../../services/auth/cancellation';
import {
  awaitOAuthCallback,
  startFixedPortOAuthCallbackServer,
} from '../../services/auth/oauthLoopback';
import type { ConnectedAccount } from '../../domain/platform/types';

const FIXED_PORT = 53987;
const AUTH_ENDPOINT = 'https://x.com/i/oauth2/authorize';
const TOKEN_ENDPOINT = 'https://api.x.com/2/oauth2/token';
const REVOKE_ENDPOINT = 'https://api.x.com/2/oauth2/revoke';
const USER_INFO_ENDPOINT = 'https://api.x.com/2/users/me';
const SCOPES = 'tweet.read tweet.write users.read media.write offline.access';

interface StoredCredential {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
}

interface XUser {
  id: string;
  username: string;
  name: string;
  profile_image_url?: string;
}

function clientId(): string {
  const id = import.meta.env.VITE_X_CLIENT_ID;
  if (!id) throw new Error('VITE_X_CLIENT_ID is not configured');
  return id;
}

function clientSecret(): string {
  const secret = import.meta.env.VITE_X_CLIENT_SECRET;
  if (!secret) throw new Error('VITE_X_CLIENT_SECRET is not configured');
  return secret;
}

function basicAuthHeader(): string {
  return `Basic ${btoa(`${clientId()}:${clientSecret()}`)}`;
}

async function exchangeCodeForToken(
  code: string,
  redirectUri: string,
  verifier: string,
): Promise<TokenResponse> {
  const response = await fetch(TOKEN_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      Authorization: basicAuthHeader(),
    },
    body: new URLSearchParams({
      code,
      code_verifier: verifier,
      grant_type: 'authorization_code',
      redirect_uri: redirectUri,
      client_id: clientId(),
    }),
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`token exchange failed: ${body}`);
  const token: TokenResponse = JSON.parse(body);
  if (!token.access_token) throw new Error(`token exchange returned no access_token: ${body}`);
  return token;
}

async function refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
  const response = await fetch(TOKEN_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      Authorization: basicAuthHeader(),
    },
    body: new URLSearchParams({
      refresh_token: refreshToken,
      grant_type: 'refresh_token',
      client_id: clientId(),
    }),
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`token refresh failed: ${body}`);
  const token: TokenResponse = JSON.parse(body);
  if (!token.access_token) throw new Error(`token refresh returned no access_token: ${body}`);
  return token;
}

async function fetchOwnUser(accessToken: string): Promise<XUser> {
  const response = await fetch(`${USER_INFO_ENDPOINT}?user.fields=profile_image_url`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) throw new Error(`failed to fetch user info: ${await response.text()}`);
  const body = await response.json();
  const user = body.data;
  if (!user) throw new Error('no X user info returned for this account');
  return user;
}

function toConnectedAccount(user: XUser): ConnectedAccount {
  return {
    id: `x:${user.id}`,
    platform: 'x',
    displayName: user.username,
    avatarUrl: user.profile_image_url,
  };
}

function toStoredCredential(token: TokenResponse, previousRefreshToken?: string): StoredCredential {
  return {
    accessToken: token.access_token,
    refreshToken: token.refresh_token ?? previousRefreshToken ?? '',
    expiresAt: Date.now() + token.expires_in * 1000,
  };
}

export class XAuth implements PlatformAuth {
  async connect(signal?: AbortSignal): Promise<ConnectedAccount> {
    return withOAuthCancellation('X', signal, async (throwIfCancelled) => {
      const port = await startFixedPortOAuthCallbackServer(FIXED_PORT);
      const redirectUri = `http://127.0.0.1:${port}`;

      const verifier = generateCodeVerifier();
      const challenge = await generateCodeChallenge(verifier);

      const authorizeUrl = new URL(AUTH_ENDPOINT);
      authorizeUrl.searchParams.set('client_id', clientId());
      authorizeUrl.searchParams.set('redirect_uri', redirectUri);
      authorizeUrl.searchParams.set('response_type', 'code');
      authorizeUrl.searchParams.set('scope', SCOPES);
      authorizeUrl.searchParams.set('code_challenge', challenge);
      authorizeUrl.searchParams.set('code_challenge_method', 'S256');
      authorizeUrl.searchParams.set('state', crypto.randomUUID());

      throwIfCancelled();
      await openUrl(authorizeUrl.toString());

      const callback = await awaitOAuthCallback();
      throwIfCancelled();
      if (callback.error || !callback.code) {
        throw new Error(
          `X authorization was not completed: ${callback.error ?? 'no code returned'}`,
        );
      }

      const token = await exchangeCodeForToken(callback.code, redirectUri, verifier);
      const user = await fetchOwnUser(token.access_token);
      const account = toConnectedAccount(user);

      await storeCredential(account.id, JSON.stringify(toStoredCredential(token)));
      return account;
    });
  }

  async disconnect(accountId: string): Promise<void> {
    try {
      const stored: StoredCredential = JSON.parse(await getCredential(accountId));
      await fetch(REVOKE_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          Authorization: basicAuthHeader(),
        },
        body: new URLSearchParams({
          token: stored.accessToken,
          token_type_hint: 'access_token',
        }),
      });
    } catch {
      // best-effort revoke; the credential is deleted locally regardless
    }
    await deleteCredential(accountId);
  }

  async getAccount(): Promise<ConnectedAccount> {
    throw new Error('XAuth.getAccount requires an accountId; read from Redux state instead');
  }

  async getValidAccessToken(accountId: string): Promise<string> {
    const stored: StoredCredential = JSON.parse(await getCredential(accountId));
    if (Date.now() < stored.expiresAt - 60_000) return stored.accessToken;

    const refreshed = await refreshAccessToken(stored.refreshToken);
    const next = toStoredCredential(refreshed, stored.refreshToken);
    await storeCredential(accountId, JSON.stringify(next));
    return next.accessToken;
  }
}
