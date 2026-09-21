import type { PlatformSettings } from '../../domain/platform/types';

export type TikTokSettings = {
  disableDuet: boolean;
  disableComment: boolean;
  disableStitch: boolean;
  isAigc: boolean;
  brandOrganicToggle: boolean;
  coverFrameSeconds: number;
};

export const TIKTOK_DEFAULT_SETTINGS: TikTokSettings = {
  disableDuet: false,
  disableComment: false,
  disableStitch: false,
  isAigc: false,
  brandOrganicToggle: false,
  coverFrameSeconds: 0,
};

export function tiktokSettingsOf(settings: PlatformSettings): TikTokSettings {
  const coverFrameSeconds = Number(settings.coverFrameSeconds);

  return {
    disableDuet: Boolean(settings.disableDuet),
    disableComment: Boolean(settings.disableComment),
    disableStitch: Boolean(settings.disableStitch),
    isAigc: Boolean(settings.isAigc),
    brandOrganicToggle: Boolean(settings.brandOrganicToggle),
    coverFrameSeconds:
      Number.isFinite(coverFrameSeconds) && coverFrameSeconds > 0 ? coverFrameSeconds : 0,
  };
}
