import { getPersisted, setPersisted } from './AppStore';

const LANGUAGE_KEY = 'language';
const THEME_KEY = 'theme';

async function loadPersisted<T>(key: string): Promise<T | undefined> {
  try {
    return await getPersisted<T>(key);
  } catch {
    return undefined;
  }
}

export function loadPersistedLanguage(): Promise<unknown> {
  return loadPersisted<unknown>(LANGUAGE_KEY);
}

export function savePersistedLanguage(language: string): Promise<void> {
  return setPersisted(LANGUAGE_KEY, language);
}

export function loadPersistedTheme(): Promise<unknown> {
  return loadPersisted<unknown>(THEME_KEY);
}

export function savePersistedTheme(theme: string): Promise<void> {
  return setPersisted(THEME_KEY, theme);
}
