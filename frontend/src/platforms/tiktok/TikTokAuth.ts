import { openUrl } from '@tauri-apps/plugin-opener';
import type { PlatformAuth } from '../../services/auth/PlatformAuth';
import {
  deleteCredential,
  getCredential,
  storeCredential,
} from '../../services/auth/SecureStorage';
import { generateCodeVerifier } from '../../services/auth/pkce';
import { withOAuthCancellation } from '../../services/auth/cancellation';
import { awaitOAuthCallback, startOAuthCallbackServer } from '../../services/auth/oauthLoopback';
import type { ConnectedAccount } from '../../domain/platform/types';

const AUTH_ENDPOINT = 'https://www.tiktok.com/v2/auth/authorize/';
const TOKEN_ENDPOINT = 'https://open.tiktokapis.com/v2/oauth/token/';
const REVOKE_ENDPOINT = 'https://open.tiktokapis.com/v2/oauth/revoke/';
const USER_INFO_ENDPOINT =
  'https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name,avatar_url';
const SCOPES = 'user.info.basic,video.publish';

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

interface TikTokUser {
  open_id: string;
  display_name: string;
  avatar_url?: string;
}

// TikTok's PKCE implementation is non-standard: it expects code_challenge as a
// lowercase hex SHA-256 digest, not the RFC 7636 base64url encoding other
// platforms (and the shared pkce.ts helper) use.
async function generateHexCodeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

function clientKey(): string {
  const key = import.meta.env.VITE_TIKTOK_CLIENT_KEY;
  if (!key) throw new Error('VITE_TIKTOK_CLIENT_KEY is not configured');
  return key;
}

function clientSecret(): string {
  const secret = import.meta.env.VITE_TIKTOK_CLIENT_SECRET;
  if (!secret) throw new Error('VITE_TIKTOK_CLIENT_SECRET is not configured');
  return secret;
}

async function exchangeCodeForToken(
  code: string,
  redirectUri: string,
  verifier: string,
): Promise<TokenResponse> {
  const response = await fetch(TOKEN_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_key: clientKey(),
      client_secret: clientSecret(),
      code,
      code_verifier: verifier,
      grant_type: 'authorization_code',
      redirect_uri: redirectUri,
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
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_key: clientKey(),
      client_secret: clientSecret(),
      refresh_token: refreshToken,
      grant_type: 'refresh_token',
    }),
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`token refresh failed: ${body}`);
  const token: TokenResponse = JSON.parse(body);
  if (!token.access_token) throw new Error(`token refresh returned no access_token: ${body}`);
  return token;
}

async function fetchOwnUser(accessToken: string): Promise<TikTokUser> {
  const response = await fetch(USER_INFO_ENDPOINT, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) throw new Error(`failed to fetch user info: ${await response.text()}`);
  const body = await response.json();
  const user = body.data?.user;
  if (!user) throw new Error('no TikTok user info returned for this account');
  return user;
}

function toConnectedAccount(user: TikTokUser): ConnectedAccount {
  return {
    id: `tiktok:${user.open_id}`,
    platform: 'tiktok',
    displayName: user.display_name,
    avatarUrl: user.avatar_url,
  };
}

function toStoredCredential(token: TokenResponse, previousRefreshToken?: string): StoredCredential {
  return {
    accessToken: token.access_token,
    refreshToken: token.refresh_token ?? previousRefreshToken ?? '',
    expiresAt: Date.now() + token.expires_in * 1000,
  };
}

export class TikTokAuth implements PlatformAuth {
  async connect(signal?: AbortSignal): Promise<ConnectedAccount> {
    return withOAuthCancellation('TikTok', signal, async (throwIfCancelled) => {
      const port = await startOAuthCallbackServer();
      const redirectUri = `http://127.0.0.1:${port}/callback`;

      const verifier = generateCodeVerifier();
      const challenge = await generateHexCodeChallenge(verifier);

      const authorizeUrl = new URL(AUTH_ENDPOINT);
      authorizeUrl.searchParams.set('client_key', clientKey());
      authorizeUrl.searchParams.set('redirect_uri', redirectUri);
      authorizeUrl.searchParams.set('response_type', 'code');
      authorizeUrl.searchParams.set('scope', SCOPES);
      authorizeUrl.searchParams.set('code_challenge', challenge);
      authorizeUrl.searchParams.set('code_challenge_method', 'S256');

      throwIfCancelled();
      await openUrl(authorizeUrl.toString());

      const callback = await awaitOAuthCallback();
      throwIfCancelled();
      if (callback.error || !callback.code) {
        throw new Error(
          `TikTok authorization was not completed: ${callback.error ?? 'no code returned'}`,
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
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_key: clientKey(),
          client_secret: clientSecret(),
          token: stored.accessToken,
        }),
      });
    } catch {
      // best-effort revoke; the credential is deleted locally regardless
    }
    await deleteCredential(accountId);
  }

  async getAccount(): Promise<ConnectedAccount> {
    throw new Error('TikTokAuth.getAccount requires an accountId; read from Redux state instead');
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
