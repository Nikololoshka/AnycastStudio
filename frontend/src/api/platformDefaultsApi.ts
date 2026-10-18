import { baseApi } from './baseApi';
import type { CurrentUser } from './types';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../domain/platform/order';
import type { PlatformSettings } from '../domain/platform/types';
import { normalizeAllPlatformSettings } from '../platforms/settings';

export interface PlatformDefaults {
  selected: AvailablePlatform[];
  settings: Record<AvailablePlatform, PlatformSettings>;
}

interface UserResponse {
  status: string;
  user: CurrentUser;
}

export function builtInPlatformDefaults(): PlatformDefaults {
  return { selected: [...AVAILABLE_PLATFORMS], settings: normalizeAllPlatformSettings({}) };
}

function defaultsOf({ user }: UserResponse): PlatformDefaults {
  return {
    selected: AVAILABLE_PLATFORMS.filter((platform) => user.defaultPlatforms.includes(platform)),
    settings: normalizeAllPlatformSettings(user.platformDefaults),
  };
}

export const platformDefaultsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getPlatformDefaults: build.query<PlatformDefaults, void>({
      query: () => '/auth/me',
      transformResponse: defaultsOf,
      providesTags: ['PlatformDefaults'],
    }),

    updatePlatformDefaults: build.mutation<PlatformDefaults, PlatformDefaults>({
      query: ({ selected, settings }) => ({
        url: '/auth/me/preferences',
        method: 'PATCH',
        body: { defaultPlatforms: selected, platformDefaults: settings },
      }),
      transformResponse: defaultsOf,
      invalidatesTags: ['PlatformDefaults', 'Session'],
    }),
  }),
});

export const { useGetPlatformDefaultsQuery, useUpdatePlatformDefaultsMutation } =
  platformDefaultsApi;
