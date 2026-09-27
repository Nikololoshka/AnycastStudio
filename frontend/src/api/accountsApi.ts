import { baseApi } from './baseApi';
import type { Platform } from '../domain/platform/types';

export interface ConnectedAccount {
  id: number;
  platform: Platform;
  externalId: string;
  displayName: string;
  avatarUrl: string;
  status: 'active' | 'needs_reauth' | 'revoked';
  connectedAt: string;
  needsReauth: boolean;
}

interface AccountsResponse {
  status: string;
  accounts: ConnectedAccount[];
  platforms: Platform[];
}

export interface CreatorInfo {
  username: string;
  nickname: string;
  avatarUrl: string;
  privacyLevelOptions: string[];
  commentDisabled: boolean;
  duetDisabled: boolean;
  stitchDisabled: boolean;
  maxVideoPostDurationSec: number | null;
}

interface CreatorInfoResponse {
  status: string;
  creatorInfo: CreatorInfo;
}

interface ConnectResponse {
  status: string;
  authUrl: string;
}

export const accountsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getAccounts: build.query<ConnectedAccount[], void>({
      query: () => '/social/accounts',
      transformResponse: (response: AccountsResponse) => response.accounts,
      providesTags: ['Account'],
    }),

    // Returns the consent URL; the caller sends the browser there. A full
    // redirect rather than a popup, so it survives blocked third-party cookies.
    startConnect: build.mutation<string, Platform>({
      query: (platform) => ({ url: `/social/${platform}/connect`, method: 'POST' }),
      transformResponse: (response: ConnectResponse) => response.authUrl,
    }),

    getCreatorInfo: build.query<CreatorInfo, number>({
      query: (id) => `/social/accounts/${id}/creator-info`,
      transformResponse: (response: CreatorInfoResponse) => response.creatorInfo,
      providesTags: ['Account'],
    }),

    disconnectAccount: build.mutation<void, number>({
      query: (id) => ({ url: `/social/accounts/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Account'],
    }),
  }),
});

export const {
  useGetAccountsQuery,
  useGetCreatorInfoQuery,
  useStartConnectMutation,
  useDisconnectAccountMutation,
} = accountsApi;
