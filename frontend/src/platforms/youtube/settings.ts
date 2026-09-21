import type { PlatformSettings } from '../../domain/platform/types';
import { oneOf, type PlatformSelectOption } from '../selectOptions';

export type YouTubePrivacy = 'private' | 'unlisted' | 'public';
export type YouTubeLicense = 'youtube' | 'creativeCommon';

export type YouTubeSettings = {
  privacyStatus: YouTubePrivacy;
  categoryId: string;
  license: YouTubeLicense;
  madeForKids: boolean;
  notifySubscribers: boolean;
  containsSyntheticMedia: boolean;
  embeddable: boolean;
  publicStatsViewable: boolean;
  hashtagsInDescription: boolean;
};

export const YOUTUBE_DEFAULT_SETTINGS: YouTubeSettings = {
  privacyStatus: 'private',
  categoryId: '22',
  license: 'youtube',
  madeForKids: false,
  notifySubscribers: true,
  containsSyntheticMedia: false,
  embeddable: true,
  publicStatsViewable: true,
  hashtagsInDescription: true,
};

const YOUTUBE_CATEGORY_IDS = [
  '1',
  '2',
  '10',
  '15',
  '17',
  '19',
  '20',
  '22',
  '23',
  '24',
  '25',
  '26',
  '27',
  '28',
] as const;

export const YOUTUBE_PRIVACY_OPTIONS: PlatformSelectOption<YouTubePrivacy>[] = [
  { value: 'private', labelKey: 'youtube.privacy.private' },
  { value: 'unlisted', labelKey: 'youtube.privacy.unlisted' },
  { value: 'public', labelKey: 'youtube.privacy.public' },
];

export const YOUTUBE_LICENSE_OPTIONS: PlatformSelectOption<YouTubeLicense>[] = [
  { value: 'youtube', labelKey: 'youtube.license.youtube' },
  { value: 'creativeCommon', labelKey: 'youtube.license.creativeCommon' },
];

export const YOUTUBE_CATEGORY_OPTIONS: PlatformSelectOption<string>[] = YOUTUBE_CATEGORY_IDS.map(
  (value) => ({ value, labelKey: `youtube.category.${value}` }),
);

export function youtubeSettingsOf(settings: PlatformSettings): YouTubeSettings {
  return {
    privacyStatus: oneOf(
      settings.privacyStatus,
      YOUTUBE_PRIVACY_OPTIONS,
      YOUTUBE_DEFAULT_SETTINGS.privacyStatus,
    ),
    categoryId: oneOf(
      settings.categoryId,
      YOUTUBE_CATEGORY_OPTIONS,
      YOUTUBE_DEFAULT_SETTINGS.categoryId,
    ),
    license: oneOf(settings.license, YOUTUBE_LICENSE_OPTIONS, YOUTUBE_DEFAULT_SETTINGS.license),
    madeForKids: Boolean(settings.madeForKids ?? YOUTUBE_DEFAULT_SETTINGS.madeForKids),
    notifySubscribers: Boolean(
      settings.notifySubscribers ?? YOUTUBE_DEFAULT_SETTINGS.notifySubscribers,
    ),
    containsSyntheticMedia: Boolean(
      settings.containsSyntheticMedia ?? YOUTUBE_DEFAULT_SETTINGS.containsSyntheticMedia,
    ),
    embeddable: Boolean(settings.embeddable ?? YOUTUBE_DEFAULT_SETTINGS.embeddable),
    publicStatsViewable: Boolean(
      settings.publicStatsViewable ?? YOUTUBE_DEFAULT_SETTINGS.publicStatsViewable,
    ),
    hashtagsInDescription: Boolean(
      settings.hashtagsInDescription ?? YOUTUBE_DEFAULT_SETTINGS.hashtagsInDescription,
    ),
  };
}
