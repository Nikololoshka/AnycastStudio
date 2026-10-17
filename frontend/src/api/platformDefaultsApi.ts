import { baseApi } from './baseApi';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../domain/platform/order';
import type { PlatformSettings } from '../domain/platform/types';
import { normalizeAllPlatformSettings } from '../platforms/settings';
import { readStored, STORAGE_KEYS, writeStored } from '../services/storage';

export interface PlatformDefaults {
  selected: AvailablePlatform[];
  settings: Record<AvailablePlatform, PlatformSettings>;
}

export function readPlatformDefaults(): PlatformDefaults {
  const selected = readStored<unknown>(STORAGE_KEYS.defaultPlatforms);
  return {
    selected: Array.isArray(selected)
      ? AVAILABLE_PLATFORMS.filter((platform) => selected.includes(platform))
      : [...AVAILABLE_PLATFORMS],
    settings: normalizeAllPlatformSettings(readStored<unknown>(STORAGE_KEYS.platformSettings)),
  };
}

export const platformDefaultsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getPlatformDefaults: build.query<PlatformDefaults, void>({
      queryFn: () => ({ data: readPlatformDefaults() }),
      providesTags: ['PlatformDefaults'],
    }),

    updatePlatformDefaults: build.mutation<PlatformDefaults, PlatformDefaults>({
      queryFn: (defaults) => {
        writeStored(STORAGE_KEYS.defaultPlatforms, defaults.selected);
        writeStored(STORAGE_KEYS.platformSettings, defaults.settings);
        return { data: defaults };
      },
      invalidatesTags: ['PlatformDefaults'],
    }),
  }),
});

export const { useGetPlatformDefaultsQuery, useUpdatePlatformDefaultsMutation } =
  platformDefaultsApi;
