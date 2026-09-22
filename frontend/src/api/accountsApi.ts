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

    disconnectAccount: build.mutation<void, number>({
      query: (id) => ({ url: `/social/accounts/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Account'],
    }),
  }),
});

export const { useGetAccountsQuery, useStartConnectMutation, useDisconnectAccountMutation } =
  accountsApi;
