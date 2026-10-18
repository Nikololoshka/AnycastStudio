const PREFIX = 'anycast:';

export function readStored<T>(key: string): T | undefined {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw === null ? undefined : (JSON.parse(raw) as T);
  } catch {
    return undefined;
  }
}

export function writeStored<T>(key: string, value: T): void {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch (error) {
    console.warn(`Preference "${key}" not saved: browser storage is full or blocked`, error);
  }
}

export function removeStored(key: string): void {
  try {
    localStorage.removeItem(PREFIX + key);
  } catch (error) {
    console.warn(`Preference "${key}" not removed: browser storage is blocked`, error);
  }
}

export const STORAGE_KEYS = {
  language: 'language',
  theme: 'theme',
  composerDraft: 'composerDraft',
  timeZone: 'timeZone',
} as const;
