import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { BaseQueryFn, FetchArgs, FetchBaseQueryError } from '@reduxjs/toolkit/query';

const API_URL = import.meta.env.VITE_API_URL ?? '';

const UNSAFE_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'];

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

const rawBaseQuery = fetchBaseQuery({
  baseUrl: `${API_URL}/api`,
  credentials: 'same-origin',
  prepareHeaders: (headers, { type }) => {
    if (type === 'mutation') {
      headers.set('X-CSRFToken', csrfToken());
    }
    return headers;
  },
});

const baseQueryWithCsrf: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (
  args,
  api,
  extraOptions,
) => {
  const method = typeof args === 'string' ? 'GET' : (args.method ?? 'GET');
  if (UNSAFE_METHODS.includes(method) && !csrfToken()) {
    await rawBaseQuery('/auth/csrf', api, extraOptions);
  }
  return rawBaseQuery(args, api, extraOptions);
};

export const baseApi = createApi({
  reducerPath: 'api',
  baseQuery: baseQueryWithCsrf,
  tagTypes: [
    'Session',
    'Account',
    'MediaAsset',
    'Publication',
    'Draft',
    'ProfilePreferences',
    'PlatformDefaults',
  ],
  endpoints: () => ({}),
});
