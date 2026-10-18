import { baseApi } from './baseApi';
import type { CurrentUser } from './types';
import { readStored, STORAGE_KEYS, writeStored } from '../services/storage';

export const AUTO_DELETE_DAYS = [7, 30, 90] as const;

export type AutoDeleteDays = (typeof AUTO_DELETE_DAYS)[number];

export interface ProfilePreferences {
  timeZone: string;
  autoDeleteSources: { enabled: boolean; afterDays: AutoDeleteDays };
}

interface UserResponse {
  status: string;
  user: CurrentUser;
}

function storedTimeZone(): string {
  return (
    readStored<string>(STORAGE_KEYS.timeZone) ?? Intl.DateTimeFormat().resolvedOptions().timeZone
  );
}

function preferencesOf({ user }: UserResponse): ProfilePreferences {
  return {
    timeZone: storedTimeZone(),
    autoDeleteSources:
      user.mediaRetentionDays === null
        ? { enabled: false, afterDays: 30 }
        : { enabled: true, afterDays: user.mediaRetentionDays },
  };
}

export const profileApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getProfilePreferences: build.query<ProfilePreferences, void>({
      query: () => '/auth/me',
      transformResponse: preferencesOf,
      providesTags: ['ProfilePreferences'],
    }),

    updateProfilePreferences: build.mutation<ProfilePreferences, ProfilePreferences>({
      query: ({ timeZone, autoDeleteSources }) => {
        writeStored(STORAGE_KEYS.timeZone, timeZone);
        return {
          url: '/auth/me/preferences',
          method: 'PATCH',
          body: {
            mediaRetentionDays: autoDeleteSources.enabled ? autoDeleteSources.afterDays : null,
          },
        };
      },
      transformResponse: preferencesOf,
      invalidatesTags: ['ProfilePreferences', 'Session'],
    }),
  }),
});

export const { useGetProfilePreferencesQuery, useUpdateProfilePreferencesMutation } = profileApi;
