export const LANGUAGES = ['en', 'ru'] as const;

export type Language = (typeof LANGUAGES)[number];

export const FALLBACK_LANGUAGE: Language = 'en';

export function toLanguage(value: unknown): Language {
  return LANGUAGES.includes(value as Language) ? (value as Language) : FALLBACK_LANGUAGE;
}

export function detectSystemLanguage(): Language {
  return toLanguage(navigator.language.split('-')[0]);
}
