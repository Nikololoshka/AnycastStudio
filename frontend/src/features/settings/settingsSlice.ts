import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { detectSystemLanguage, toLanguage, type Language } from '../../app/i18n';
import { readStored, STORAGE_KEYS } from '../../services/storage';

export type ThemePreference = 'light' | 'dark' | 'system';

export interface SettingsState {
  language: Language;
  theme: ThemePreference;
}

const THEME_PREFERENCES: ThemePreference[] = ['light', 'dark', 'system'];

function toThemePreference(value: unknown): ThemePreference {
  return THEME_PREFERENCES.includes(value as ThemePreference)
    ? (value as ThemePreference)
    : 'system';
}

/**
 * Read straight from browser storage. These two preferences apply before the
 * first paint, so waiting for a request would show the wrong theme first.
 */
function initialSettings(): SettingsState {
  const storedLanguage = readStored<unknown>(STORAGE_KEYS.language);
  return {
    language: storedLanguage === undefined ? detectSystemLanguage() : toLanguage(storedLanguage),
    theme: toThemePreference(readStored<unknown>(STORAGE_KEYS.theme)),
  };
}

const settingsSlice = createSlice({
  name: 'settings',
  initialState: initialSettings,
  reducers: {
    changeTheme(state, action: PayloadAction<ThemePreference>) {
      state.theme = action.payload;
    },
    changeLanguage(state, action: PayloadAction<Language>) {
      state.language = action.payload;
    },
  },
});

export const { changeTheme, changeLanguage } = settingsSlice.actions;

export default settingsSlice.reducer;
