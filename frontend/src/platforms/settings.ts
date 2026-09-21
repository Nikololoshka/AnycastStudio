import type { Platform, PlatformSettings } from '../domain/platform/types';
import { instagramSettingsOf } from './instagram/settings';
import { tiktokSettingsOf } from './tiktok/settings';
import { xSettingsOf } from './x/settings';
import { youtubeSettingsOf } from './youtube/settings';

const normalizers: Record<Platform, (raw: PlatformSettings) => PlatformSettings> = {
  youtube: youtubeSettingsOf,
  x: xSettingsOf,
  instagram: instagramSettingsOf,
  tiktok: tiktokSettingsOf,
};

function isPlatformSettings(value: unknown): value is PlatformSettings {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function normalizePlatformSettings(platform: Platform, raw: unknown): PlatformSettings {
  return normalizers[platform](isPlatformSettings(raw) ? raw : {});
}

export function defaultPlatformSettings(): Record<Platform, PlatformSettings> {
  return {
    youtube: normalizePlatformSettings('youtube', undefined),
    x: normalizePlatformSettings('x', undefined),
    instagram: normalizePlatformSettings('instagram', undefined),
    tiktok: normalizePlatformSettings('tiktok', undefined),
  };
}

export function normalizeAllPlatformSettings(raw: unknown): Record<Platform, PlatformSettings> {
  const stored = isPlatformSettings(raw) ? raw : {};

  return {
    youtube: normalizePlatformSettings('youtube', stored.youtube),
    x: normalizePlatformSettings('x', stored.x),
    instagram: normalizePlatformSettings('instagram', stored.instagram),
    tiktok: normalizePlatformSettings('tiktok', stored.tiktok),
  };
}
