import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { detectSystemLanguage, toLanguage, type Language } from '../../app/i18n';
import {
  loadPersistedLanguage,
  loadPersistedTheme,
  savePersistedLanguage,
  savePersistedTheme,
} from '../../services/persistence';

export type ThemePreference = 'light' | 'dark' | 'system';

export interface SettingsState {
  language: Language;
  theme: ThemePreference;
  defaultHashtags: string[];

  maxConcurrentUploads: number;
  automaticRetryCount: number;
  chunkSize: number;
  bandwidthLimit?: number;

  timezone: string;
}

const THEME_PREFERENCES: ThemePreference[] = ['light', 'dark', 'system'];

function toThemePreference(value: unknown, fallback: ThemePreference): ThemePreference {
  return THEME_PREFERENCES.includes(value as ThemePreference)
    ? (value as ThemePreference)
    : fallback;
}

const initialState: SettingsState = {
  language: 'en',
  theme: 'system',
  defaultHashtags: [],
  maxConcurrentUploads: 4,
  automaticRetryCount: 3,
  chunkSize: 0,
  timezone: 'UTC',
};

export const restoreAppSettings = createAsyncThunk<{
  language: Language;
  theme: ThemePreference;
}>('settings/restoreAppSettings', async () => {
  const [storedLanguage, storedTheme] = await Promise.all([
    loadPersistedLanguage(),
    loadPersistedTheme(),
  ]);

  return {
    language: storedLanguage === undefined ? detectSystemLanguage() : toLanguage(storedLanguage),
    theme: toThemePreference(storedTheme, initialState.theme),
  };
});

export const changeLanguage = createAsyncThunk<void, Language>(
  'settings/changeLanguage',
  async (language, { dispatch }) => {
    dispatch(setLanguage(language));
    await savePersistedLanguage(language);
  },
);

export const changeTheme = createAsyncThunk<void, ThemePreference>(
  'settings/changeTheme',
  async (theme, { dispatch }) => {
    dispatch(setTheme(theme));
    await savePersistedTheme(theme);
  },
);

const settingsSlice = createSlice({
  name: 'settings',
  initialState,
  reducers: {
    setTheme(state, action: PayloadAction<ThemePreference>) {
      state.theme = action.payload;
    },
    setLanguage(state, action: PayloadAction<Language>) {
      state.language = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder.addCase(restoreAppSettings.fulfilled, (state, action) => {
      state.language = action.payload.language;
      state.theme = action.payload.theme;
    });
  },
});

export const { setTheme, setLanguage } = settingsSlice.actions;

export default settingsSlice.reducer;
