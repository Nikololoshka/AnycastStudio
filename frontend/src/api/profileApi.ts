import { baseApi } from './baseApi';
import { readStored, STORAGE_KEYS, writeStored } from '../services/storage';

export const AUTO_DELETE_DAYS = [7, 30, 90] as const;

export type AutoDeleteDays = (typeof AUTO_DELETE_DAYS)[number];

export interface ProfilePreferences {
  timeZone: string;
  autoDeleteSources: { enabled: boolean; afterDays: AutoDeleteDays };
  notifications: {
    published: boolean;
    failed: boolean;
    storageAlmostFull: boolean;
    weeklyDigest: boolean;
  };
}

export interface UserSession {
  id: string;
  device: string;
  lastActiveAt: string;
  isCurrent: boolean;
}

const HOUR_MS = 60 * 60 * 1000;

function defaultPreferences(): ProfilePreferences {
  return {
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    autoDeleteSources: { enabled: false, afterDays: 30 },
    notifications: { published: true, failed: true, storageAlmostFull: false, weeklyDigest: false },
  };
}

function currentDevice(): string {
  const agent = navigator.userAgent;
  const browser = ['Edg', 'OPR', 'Firefox', 'Chrome', 'Safari']
    .find((name) => agent.includes(name))
    ?.replace('Edg', 'Edge')
    .replace('OPR', 'Opera');
  const system = ['Windows', 'Android', 'iPhone', 'iPad', 'Mac', 'Linux']
    .find((name) => agent.includes(name))
    ?.replace('Mac', 'macOS');
  return [browser, system].filter(Boolean).join(' · ');
}

function mockSessions(): UserSession[] {
  const now = Date.now();
  const ended = readStored<string[]>(STORAGE_KEYS.endedSessions) ?? [];
  return [
    {
      id: 'current',
      device: currentDevice(),
      lastActiveAt: new Date(now).toISOString(),
      isCurrent: true,
    },
    {
      id: 'phone',
      device: 'Safari · iPhone',
      lastActiveAt: new Date(now - 3 * HOUR_MS).toISOString(),
      isCurrent: false,
    },
    {
      id: 'laptop',
      device: 'Firefox · Linux',
      lastActiveAt: new Date(now - 52 * HOUR_MS).toISOString(),
      isCurrent: false,
    },
  ].filter((session) => !ended.includes(session.id));
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

    getSessions: build.query<UserSession[], void>({
      queryFn: () => ({ data: mockSessions() }),
      providesTags: ['UserSession'],
    }),

    endSession: build.mutation<null, string>({
      queryFn: (id) => {
        const ended = readStored<string[]>(STORAGE_KEYS.endedSessions) ?? [];
        writeStored(STORAGE_KEYS.endedSessions, [...ended, id]);
        return { data: null };
      },
      invalidatesTags: ['UserSession'],
    }),
  }),
});

export const {
  useEndSessionMutation,
  useGetProfilePreferencesQuery,
  useGetSessionsQuery,
  useUpdateProfilePreferencesMutation,
} = profileApi;
