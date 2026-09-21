import type {
  Platform,
  PlatformCapabilities,
  PlatformSettings,
  SchedulingMode,
} from '../domain/platform/types';
import type { PlatformAdapter } from './PlatformAdapter';
import { YouTubeAdapter } from './youtube';
import { XAdapter } from './x';
import { InstagramAdapter } from './instagram';
import { TikTokAdapter } from './tiktok';

const adapters: Record<Platform, PlatformAdapter> = {
  youtube: new YouTubeAdapter(),
  x: new XAdapter(),
  instagram: new InstagramAdapter(),
  tiktok: new TikTokAdapter(),
};

export function getCapabilitiesFor(platform: Platform): PlatformCapabilities {
  return adapters[platform].getCapabilities();
}

export function getLabelFor(platform: Platform): string {
  return getCapabilitiesFor(platform).label;
}

export function getAdapterFor(platform: Platform): PlatformAdapter {
  return adapters[platform];
}

export interface SchedulingProfile {
  mode: SchedulingMode;
  stagedMediaTtlMs?: number;
}

export function getSchedulingProfileFor(
  platform: Platform,
  settings: PlatformSettings,
): SchedulingProfile {
  const adapter = adapters[platform];
  const capabilities = adapter.getCapabilities();

  return {
    mode: adapter.getSchedulingMode?.(settings) ?? capabilities.scheduling,
    stagedMediaTtlMs: capabilities.stagedMediaTtlMs,
  };
}
