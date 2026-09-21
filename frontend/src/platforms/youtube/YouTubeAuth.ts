import { openUrl } from '@tauri-apps/plugin-opener';
import type { PlatformAuth } from '../../services/auth/PlatformAuth';
import {
  deleteCredential,
  getCredential,
  storeCredential,
} from '../../services/auth/SecureStorage';
import { generateCodeChallenge, generateCodeVerifier } from '../../services/auth/pkce';
import { withOAuthCancellation } from '../../services/auth/cancellation';
import { awaitOAuthCallback, startOAuthCallbackServer } from '../../services/auth/oauthLoopback';
import type { ConnectedAccount } from '../../domain/platform/types';

const AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth';
const TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token';
const REVOKE_ENDPOINT = 'https://oauth2.googleapis.com/revoke';
const SCOPES = [
  'https://www.googleapis.com/auth/youtube.upload',
  'https://www.googleapis.com/auth/youtube',
].join(' ');

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

interface YouTubeChannel {
  id: string;
  snippet: { title: string; thumbnails?: { default?: { url?: string } } };
}

function clientId(): string {
  const id = import.meta.env.VITE_YOUTUBE_CLIENT_ID;
  if (!id) throw new Error('VITE_YOUTUBE_CLIENT_ID is not configured');
  return id;
}

function clientSecret(): string {
  const secret = import.meta.env.VITE_YOUTUBE_CLIENT_SECRET;
  if (!secret) throw new Error('VITE_YOUTUBE_CLIENT_SECRET is not configured');
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
      client_id: clientId(),
      client_secret: clientSecret(),
      code,
      code_verifier: verifier,
      grant_type: 'authorization_code',
      redirect_uri: redirectUri,
    }),
  });
  if (!response.ok) throw new Error(`token exchange failed: ${await response.text()}`);
  return response.json();
}

async function refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
  const response = await fetch(TOKEN_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: clientId(),
      client_secret: clientSecret(),
      refresh_token: refreshToken,
      grant_type: 'refresh_token',
    }),
  });
  if (!response.ok) throw new Error(`token refresh failed: ${await response.text()}`);
  return response.json();
}

async function fetchOwnChannel(accessToken: string): Promise<YouTubeChannel> {
  const response = await fetch(
    'https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true',
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
  if (!response.ok) throw new Error(`failed to fetch channel: ${await response.text()}`);
  const body = await response.json();
  const channel = body.items?.[0];
  if (!channel) throw new Error('no YouTube channel found for this account');
  return channel;
}

function toConnectedAccount(channel: YouTubeChannel): ConnectedAccount {
  return {
    id: `youtube:${channel.id}`,
    platform: 'youtube',
    displayName: channel.snippet.title,
    avatarUrl: channel.snippet.thumbnails?.default?.url,
  };
}

function toStoredCredential(token: TokenResponse, previousRefreshToken?: string): StoredCredential {
  return {
    accessToken: token.access_token,
    refreshToken: token.refresh_token ?? previousRefreshToken ?? '',
    expiresAt: Date.now() + token.expires_in * 1000,
  };
}

export class YouTubeAuth implements PlatformAuth {
  async connect(signal?: AbortSignal): Promise<ConnectedAccount> {
    return withOAuthCancellation('YouTube', signal, async (throwIfCancelled) => {
      const port = await startOAuthCallbackServer();
      const redirectUri = `http://127.0.0.1:${port}/callback`;

      const verifier = generateCodeVerifier();
      const challenge = await generateCodeChallenge(verifier);

      const authorizeUrl = new URL(AUTH_ENDPOINT);
      authorizeUrl.searchParams.set('client_id', clientId());
      authorizeUrl.searchParams.set('redirect_uri', redirectUri);
      authorizeUrl.searchParams.set('response_type', 'code');
      authorizeUrl.searchParams.set('scope', SCOPES);
      authorizeUrl.searchParams.set('code_challenge', challenge);
      authorizeUrl.searchParams.set('code_challenge_method', 'S256');
      authorizeUrl.searchParams.set('access_type', 'offline');
      authorizeUrl.searchParams.set('prompt', 'consent');

      throwIfCancelled();
      await openUrl(authorizeUrl.toString());

      const callback = await awaitOAuthCallback();
      throwIfCancelled();
      if (callback.error || !callback.code) {
        throw new Error(
          `YouTube authorization was not completed: ${callback.error ?? 'no code returned'}`,
        );
      }

      const token = await exchangeCodeForToken(callback.code, redirectUri, verifier);
      const channel = await fetchOwnChannel(token.access_token);
      const account = toConnectedAccount(channel);

      await storeCredential(account.id, JSON.stringify(toStoredCredential(token)));
      return account;
    });
  }

  async disconnect(accountId: string): Promise<void> {
    try {
      const stored: StoredCredential = JSON.parse(await getCredential(accountId));
      await fetch(
        `${REVOKE_ENDPOINT}?token=${encodeURIComponent(stored.refreshToken || stored.accessToken)}`,
        {
          method: 'POST',
        },
      );
    } catch {
      // best-effort revoke; the credential is deleted locally regardless
    }
    await deleteCredential(accountId);
  }

  async getAccount(): Promise<ConnectedAccount> {
    throw new Error('YouTubeAuth.getAccount requires an accountId; read from Redux state instead');
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
