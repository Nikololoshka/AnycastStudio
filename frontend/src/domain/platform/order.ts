import type { Platform } from './types';

export const PLATFORMS: Platform[] = ['youtube', 'x', 'tiktok', 'instagram'];

export function getShortcutFor(platform: Platform): string {
  return `Alt+${PLATFORMS.indexOf(platform) + 1}`;
}
