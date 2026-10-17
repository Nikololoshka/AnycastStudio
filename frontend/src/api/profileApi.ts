import { baseApi } from './baseApi';
import { readStored, STORAGE_KEYS, writeStored } from '../services/storage';

export const AUTO_DELETE_DAYS = [7, 30, 90] as const;

export type AutoDeleteDays = (typeof AUTO_DELETE_DAYS)[number];

export interface ProfilePreferences {
  timeZone: string;
  autoDeleteSources: { enabled: boolean; afterDays: AutoDeleteDays };
}

function defaultPreferences(): ProfilePreferences {
  return {
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    autoDeleteSources: { enabled: false, afterDays: 30 },
  };
}

export const profileApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getProfilePreferences: build.query<ProfilePreferences, void>({
      queryFn: () => ({
        data: {
          ...defaultPreferences(),
          ...readStored<ProfilePreferences>(STORAGE_KEYS.profilePreferences),
        },
      }),
      providesTags: ['ProfilePreferences'],
    }),

    updateProfilePreferences: build.mutation<ProfilePreferences, ProfilePreferences>({
      queryFn: (preferences) => {
        writeStored(STORAGE_KEYS.profilePreferences, preferences);
        return { data: preferences };
      },
      invalidatesTags: ['ProfilePreferences'],
    }),
  }),
});

export const {
  useGetProfilePreferencesQuery,
  useUpdateProfilePreferencesMutation,
} = profileApi;
