import type { Platform, PlatformSettings } from '../../domain/platform/types';
import { getPersisted, setPersisted } from './AppStore';

const PLATFORM_SETTINGS_KEY = 'platformSettings';

export async function loadPersistedPlatformSettings(): Promise<unknown> {
  try {
    return await getPersisted<unknown>(PLATFORM_SETTINGS_KEY);
  } catch {
    return undefined;
  }
}

export async function savePersistedPlatformSettings(
  settings: Record<Platform, PlatformSettings>,
): Promise<void> {
  await setPersisted(PLATFORM_SETTINGS_KEY, settings);
}
