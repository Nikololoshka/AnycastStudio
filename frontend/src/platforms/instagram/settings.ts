import type { PlatformSettings } from '../../domain/platform/types';

export type InstagramSettings = {
  shareToFeed: boolean;
  coverFrameSeconds: number;
};

export const INSTAGRAM_DEFAULT_SETTINGS: InstagramSettings = {
  shareToFeed: true,
  coverFrameSeconds: 0,
};

export function instagramSettingsOf(settings: PlatformSettings): InstagramSettings {
  const coverFrameSeconds = Number(settings.coverFrameSeconds);

  return {
    shareToFeed: Boolean(settings.shareToFeed ?? INSTAGRAM_DEFAULT_SETTINGS.shareToFeed),
    coverFrameSeconds:
      Number.isFinite(coverFrameSeconds) && coverFrameSeconds > 0 ? coverFrameSeconds : 0,
  };
}
