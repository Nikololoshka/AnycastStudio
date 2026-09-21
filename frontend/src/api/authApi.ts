import { baseApi } from './baseApi';
import type { CurrentUser } from './types';

interface Credentials {
  email: string;
  password: string;
}

interface SessionResponse {
  status: string;
  user: CurrentUser;
}

export const authApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getSession: build.query<CurrentUser | null, void>({
      query: () => '/auth/me',
      transformResponse: (response: SessionResponse) => response.user,
      // A signed-out visitor is not an error worth showing; the router redirects.
      transformErrorResponse: () => null,
      providesTags: ['Session'],
    }),

    login: build.mutation<CurrentUser, Credentials>({
      query: (credentials) => ({ url: '/auth/login', method: 'POST', body: credentials }),
      transformResponse: (response: SessionResponse) => response.user,
      invalidatesTags: ['Session'],
    }),

    logout: build.mutation<void, void>({
      query: () => ({ url: '/auth/logout', method: 'POST' }),
      invalidatesTags: ['Session', 'Account', 'MediaAsset', 'Publication'],
    }),
  }),
});

export const { useGetSessionQuery, useLoginMutation, useLogoutMutation } = authApi;
