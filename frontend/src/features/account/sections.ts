export const ACCOUNT_SECTIONS = [
  'profile',
  'storage',
  'notifications',
  'security',
  'danger',
] as const;

export type AccountSection = (typeof ACCOUNT_SECTIONS)[number];
