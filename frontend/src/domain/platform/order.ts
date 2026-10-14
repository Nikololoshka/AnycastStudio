import type { Platform } from './types';

export const AVAILABLE_PLATFORMS = ['youtube', 'tiktok', 'instagram', 'x'] as const;

export type AvailablePlatform = (typeof AVAILABLE_PLATFORMS)[number];

export function isAvailable(platform: Platform): platform is AvailablePlatform {
  return (AVAILABLE_PLATFORMS as readonly Platform[]).includes(platform);
}
