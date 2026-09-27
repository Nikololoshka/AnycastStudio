import type { PlatformSettings } from '../../domain/platform/types';
import type { DraftError } from '../PlatformDescriptor';
import type { PlatformSelectOption } from '../selectOptions';

export type TikTokPrivacy =
  'PUBLIC_TO_EVERYONE' | 'MUTUAL_FOLLOW_FRIENDS' | 'FOLLOWER_OF_CREATOR' | 'SELF_ONLY';

export type TikTokSettings = {
  privacyLevel: TikTokPrivacy | null;
  disableComment: boolean;
  disableDuet: boolean;
  disableStitch: boolean;
  discloseContent: boolean;
  brandOrganic: boolean;
  brandContent: boolean;
  isAigc: boolean;
  coverFrameSeconds: number;
};

export const TIKTOK_DEFAULT_SETTINGS: TikTokSettings = {
  privacyLevel: null,
  disableComment: false,
  disableDuet: false,
  disableStitch: false,
  discloseContent: false,
  brandOrganic: false,
  brandContent: false,
  isAigc: false,
  coverFrameSeconds: 0,
};

export const TIKTOK_MAX_CAPTION_LENGTH = 2200;

export const TIKTOK_PRIVACY_OPTIONS: PlatformSelectOption<TikTokPrivacy>[] = [
  { value: 'PUBLIC_TO_EVERYONE', labelKey: 'tiktok.privacy.PUBLIC_TO_EVERYONE' },
  { value: 'MUTUAL_FOLLOW_FRIENDS', labelKey: 'tiktok.privacy.MUTUAL_FOLLOW_FRIENDS' },
  { value: 'FOLLOWER_OF_CREATOR', labelKey: 'tiktok.privacy.FOLLOWER_OF_CREATOR' },
  { value: 'SELF_ONLY', labelKey: 'tiktok.privacy.SELF_ONLY' },
];

function privacyOf(value: unknown): TikTokPrivacy | null {
  return TIKTOK_PRIVACY_OPTIONS.find((option) => option.value === value)?.value ?? null;
}

function secondsOf(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0;
}

export function tiktokSettingsOf(settings: PlatformSettings): TikTokSettings {
  return {
    privacyLevel: privacyOf(settings.privacyLevel),
    disableComment: Boolean(settings.disableComment),
    disableDuet: Boolean(settings.disableDuet),
    disableStitch: Boolean(settings.disableStitch),
    discloseContent: Boolean(settings.discloseContent),
    brandOrganic: Boolean(settings.brandOrganic),
    brandContent: Boolean(settings.brandContent),
    isAigc: Boolean(settings.isAigc),
    coverFrameSeconds: secondsOf(settings.coverFrameSeconds),
  };
}

export function tiktokStoredSettingsOf(settings: PlatformSettings): TikTokSettings {
  return { ...tiktokSettingsOf(settings), privacyLevel: null };
}

export function tiktokCaptionOf(title: string, description: string, hashtags: string[]): string {
  const tags = hashtags.map((tag) => `#${tag}`).join(' ');
  return [title.trim(), description.trim(), tags].filter(Boolean).join('\n\n');
}

export function tiktokSettingErrors(settings: TikTokSettings): DraftError[] {
  const errors: DraftError[] = [];
  if (settings.privacyLevel === null) {
    errors.push('privacyRequired');
  }
  if (settings.discloseContent && !settings.brandOrganic && !settings.brandContent) {
    errors.push('commercialContentUnspecified');
  }
  if (settings.discloseContent && settings.brandContent && settings.privacyLevel === 'SELF_ONLY') {
    errors.push('brandedContentCannotBePrivate');
  }
  return errors;
}
