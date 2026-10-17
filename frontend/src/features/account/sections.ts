export const ACCOUNT_SECTIONS = [
  'profile',
  'storage',
] as const;

export type AccountSection = (typeof ACCOUNT_SECTIONS)[number];
