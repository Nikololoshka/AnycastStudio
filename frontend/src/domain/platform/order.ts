import type { Platform } from './types';

/** Every platform the product covers. The server uses the same names. */
export const PLATFORMS: Platform[] = ['youtube', 'x', 'tiktok', 'instagram'];

/**
 * Platforms this release can publish to. The others are ported one by one;
 * until then nothing may offer them.
 */
export const AVAILABLE_PLATFORMS = ['youtube', 'tiktok', 'instagram'] as const;

export type AvailablePlatform = (typeof AVAILABLE_PLATFORMS)[number];

export function isAvailable(platform: Platform): platform is AvailablePlatform {
  return (AVAILABLE_PLATFORMS as readonly Platform[]).includes(platform);
}

export function getShortcutFor(platform: AvailablePlatform): string {
  return `Alt+${AVAILABLE_PLATFORMS.indexOf(platform) + 1}`;
}
