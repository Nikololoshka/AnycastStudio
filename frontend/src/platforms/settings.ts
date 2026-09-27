import type { PlatformSettings } from '../domain/platform/types';
import type { AvailablePlatform } from '../domain/platform/order';
import { instagramSettingsOf } from './instagram/settings';
import { tiktokSettingsOf, tiktokStoredSettingsOf } from './tiktok/settings';
import { youtubeSettingsOf } from './youtube/settings';

const normalizers: Record<AvailablePlatform, (raw: PlatformSettings) => PlatformSettings> = {
  youtube: youtubeSettingsOf,
  tiktok: tiktokSettingsOf,
  instagram: instagramSettingsOf,
};

function isPlatformSettings(value: unknown): value is PlatformSettings {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function normalizePlatformSettings(
  platform: AvailablePlatform,
  raw: unknown,
): PlatformSettings {
  return normalizers[platform](isPlatformSettings(raw) ? raw : {});
}

export function defaultPlatformSettings(): Record<AvailablePlatform, PlatformSettings> {
  return {
    youtube: normalizePlatformSettings('youtube', undefined),
    tiktok: normalizePlatformSettings('tiktok', undefined),
    instagram: normalizePlatformSettings('instagram', undefined),
  };
}

export function normalizeAllPlatformSettings(
  raw: unknown,
): Record<AvailablePlatform, PlatformSettings> {
  const stored = isPlatformSettings(raw) ? raw : {};
  return {
    youtube: normalizePlatformSettings('youtube', stored.youtube),
    tiktok: tiktokStoredSettingsOf(isPlatformSettings(stored.tiktok) ? stored.tiktok : {}),
    instagram: normalizePlatformSettings('instagram', stored.instagram),
  };
}
