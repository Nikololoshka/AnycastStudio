import { fetch } from '@tauri-apps/plugin-http';
import type { PlatformAuth } from '../../services/auth/PlatformAuth';
import {
  deleteCredential,
  getCredential,
  storeCredential,
} from '../../services/auth/SecureStorage';
import type { ConnectedAccount } from '../../domain/platform/types';
import { withOAuthCancellation } from '../../services/auth/cancellation';
import { signInWithFacebook, type FacebookUserToken } from './facebookLoginBroker';

const GRAPH_VERSION = 'v23.0';
const GRAPH_BASE = `https://graph.facebook.com/${GRAPH_VERSION}`;
const ACCOUNTS_ENDPOINT = `${GRAPH_BASE}/me/accounts`;
const PERMISSIONS_ENDPOINT = `${GRAPH_BASE}/me/permissions`;
const DEBUG_TOKEN_ENDPOINT = `${GRAPH_BASE}/debug_token`;
const PAGE_FIELDS =
  'id,access_token,instagram_business_account{id,username,profile_picture_url},connected_instagram_account{id,username,profile_picture_url}';

const DEFAULT_LONG_LIVED_LIFETIME_SECONDS = 60 * 24 * 60 * 60;

interface StoredCredential {
  userAccessToken: string;
  pageAccessToken: string;
  obtainedAt: number;
  expiresAt: number;
}

interface InstagramBusinessAccount {
  id: string;
  username: string;
  profile_picture_url?: string;
}

interface PageEntry {
  id: string;
  access_token: string;
  instagram_business_account?: InstagramBusinessAccount;
  connected_instagram_account?: InstagramBusinessAccount;
}

interface GranularScope {
  scope: string;
  target_ids?: string[];
}

interface LinkedInstagramAccount {
  instagram: InstagramBusinessAccount;
  pageAccessToken: string;
}

function instagramAccountOf(page: PageEntry): InstagramBusinessAccount | undefined {
  return page.instagram_business_account ?? page.connected_instagram_account;
}

async function listPagesFromAccounts(userAccessToken: string): Promise<PageEntry[]> {
  const url = new URL(ACCOUNTS_ENDPOINT);
  url.searchParams.set('fields', PAGE_FIELDS);
  url.searchParams.set('access_token', userAccessToken);

  const response = await fetch(url.toString());
  const body = await response.text();
  if (!response.ok) throw new Error(`failed to list Facebook Pages: ${body}`);

  return JSON.parse(body).data ?? [];
}

async function assetIdsFromTokenScopes(userAccessToken: string): Promise<string[]> {
  const url = new URL(DEBUG_TOKEN_ENDPOINT);
  url.searchParams.set('input_token', userAccessToken);
  url.searchParams.set('access_token', userAccessToken);

  const response = await fetch(url.toString());
  if (!response.ok) return [];

  const scopes: GranularScope[] = (await response.json()).data?.granular_scopes ?? [];
  return [...new Set(scopes.flatMap((scope) => scope.target_ids ?? []))];
}

async function fetchPage(pageId: string, userAccessToken: string): Promise<PageEntry | undefined> {
  const url = new URL(`${GRAPH_BASE}/${pageId}`);
  url.searchParams.set('fields', PAGE_FIELDS);
  url.searchParams.set('access_token', userAccessToken);

  const response = await fetch(url.toString());
  if (!response.ok) return undefined;

  const page: PageEntry = await response.json();
  return page.access_token ? page : undefined;
}

async function listCandidatePages(userAccessToken: string): Promise<PageEntry[]> {
  const listed = await listPagesFromAccounts(userAccessToken);
  if (listed.length > 0) return listed;

  const assetIds = await assetIdsFromTokenScopes(userAccessToken);
  const pages = await Promise.all(assetIds.map((id) => fetchPage(id, userAccessToken)));
  return pages.filter((page): page is PageEntry => Boolean(page));
}

async function findLinkedInstagramAccount(
  userAccessToken: string,
): Promise<LinkedInstagramAccount> {
  const pages = await listCandidatePages(userAccessToken);
  const linked = pages.find((page) => instagramAccountOf(page));
  const instagram = linked && instagramAccountOf(linked);

  if (!linked || !instagram) {
    throw new Error(
      'No Facebook Page with a linked Instagram professional account was found for this user',
    );
  }

  return { instagram, pageAccessToken: linked.access_token };
}

function toConnectedAccount(instagram: InstagramBusinessAccount): ConnectedAccount {
  return {
    id: `instagram:${instagram.id}`,
    platform: 'instagram',
    displayName: instagram.username,
    avatarUrl: instagram.profile_picture_url,
  };
}

function toStoredCredential(
  userToken: FacebookUserToken,
  pageAccessToken: string,
): StoredCredential {
  const obtainedAt = Date.now();
  const lifetimeSeconds = userToken.expiresIn ?? DEFAULT_LONG_LIVED_LIFETIME_SECONDS;
  return {
    userAccessToken: userToken.accessToken,
    pageAccessToken,
    obtainedAt,
    expiresAt: obtainedAt + lifetimeSeconds * 1000,
  };
}

export class InstagramAuth implements PlatformAuth {
  async connect(signal?: AbortSignal): Promise<ConnectedAccount> {
    return withOAuthCancellation('Instagram', signal, async (throwIfCancelled) => {
      const userToken = await signInWithFacebook(throwIfCancelled, signal);
      const linked = await findLinkedInstagramAccount(userToken.accessToken);
      const account = toConnectedAccount(linked.instagram);

      await storeCredential(
        account.id,
        JSON.stringify(toStoredCredential(userToken, linked.pageAccessToken)),
      );
      return account;
    });
  }

  async disconnect(accountId: string): Promise<void> {
    try {
      const stored: StoredCredential = JSON.parse(await getCredential(accountId));
      const url = new URL(PERMISSIONS_ENDPOINT);
      url.searchParams.set('access_token', stored.userAccessToken);
      await fetch(url.toString(), { method: 'DELETE' });
    } catch {
      await deleteCredential(accountId);
      return;
    }
    await deleteCredential(accountId);
  }

  async getAccount(): Promise<ConnectedAccount> {
    throw new Error(
      'InstagramAuth.getAccount requires an accountId; read from Redux state instead',
    );
  }

  async getValidAccessToken(accountId: string): Promise<string> {
    const stored: StoredCredential = JSON.parse(await getCredential(accountId));
    if (stored.expiresAt <= Date.now()) {
      throw new Error('Instagram sign-in has expired; reconnect the account');
    }
    return stored.pageAccessToken;
  }
}
