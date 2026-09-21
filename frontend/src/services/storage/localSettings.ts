/**
 * Per-viewer preferences kept in the browser.
 *
 * Only what is cheap to lose belongs here: the theme, the language and the
 * composer draft. Anything the server must know goes to the server. Every
 * access is guarded because storage throws in a private window and can come
 * back empty after the person clears site data.
 */

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
  } catch {
    // Storage is full or blocked. The preference is not worth failing over.
  }
}

export function removeStored(key: string): void {
  try {
    localStorage.removeItem(PREFIX + key);
  } catch {
    // See writeStored.
  }
}

export const STORAGE_KEYS = {
  language: 'language',
  theme: 'theme',
  platformSettings: 'platformSettings',
  composerDraft: 'composerDraft',
} as const;
