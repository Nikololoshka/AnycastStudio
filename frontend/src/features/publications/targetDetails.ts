import type { ParseKeys, TFunction } from 'i18next';
import type { Publication } from '../../api/publicationsApi';
import type { AvailablePlatform } from '../../domain/platform/order';
import type { PlatformSettings } from '../../domain/platform/types';
import { instagramCaptionOf } from '../../platforms/instagram/settings';
import { normalizePlatformSettings } from '../../platforms/settings';
import { tiktokCaptionOf } from '../../platforms/tiktok/settings';
import { xCaptionOf } from '../../platforms/x/settings';
import { youtubeDescriptionOf, youtubeSettingsOf } from '../../platforms/youtube/settings';

export interface SettingRow {
  key: string;
  label: string;
  value: string | number | boolean;
  isChanged: boolean;
}

export interface TextPart {
  kind: 'title' | 'description' | 'caption';
  text: string;
}

const LABEL_KEY: Record<string, string> = {
  privacyStatus: 'privacy',
  categoryId: 'category',
  privacyLevel: 'privacy',
};

const CAPTION: Record<
  Exclude<AvailablePlatform, 'youtube'>,
  (title: string, description: string, hashtags: string[]) => string
> = {
  tiktok: tiktokCaptionOf,
  instagram: instagramCaptionOf,
  x: xCaptionOf,
};

function labelKeyOf(platform: AvailablePlatform, key: string): ParseKeys<'platforms'> {
  if (key === 'coverFrameSeconds') return 'coverFrame.label';
  return `${platform}.${LABEL_KEY[key] ?? key}.label` as ParseKeys<'platforms'>;
}

export function settingRows(
  platform: AvailablePlatform,
  raw: PlatformSettings,
  defaults: PlatformSettings | undefined,
  t: TFunction<'platforms'>,
): SettingRow[] {
  const rows = Object.entries(normalizePlatformSettings(platform, raw)).map(
    ([key, value]): SettingRow => ({
      key,
      label: t(labelKeyOf(platform, key)),
      value:
        typeof value === 'string'
          ? t(`${platform}.${LABEL_KEY[key] ?? key}.${value}` as ParseKeys<'platforms'>)
          : typeof value === 'number' || typeof value === 'boolean'
            ? value
            : '—',
      isChanged: defaults !== undefined && defaults[key] !== value,
    }),
  );
  return rows.sort(
    (a, b) => Number(typeof a.value === 'boolean') - Number(typeof b.value === 'boolean'),
  );
}

export function finalText(
  platform: AvailablePlatform,
  publication: Pick<Publication, 'title' | 'description' | 'hashtags'>,
  raw: PlatformSettings,
): TextPart[] {
  const { title, description, hashtags } = publication;
  const parts: TextPart[] =
    platform === 'youtube'
      ? [
          { kind: 'title', text: title },
          {
            kind: 'description',
            text: youtubeDescriptionOf(description, hashtags, youtubeSettingsOf(raw)),
          },
        ]
      : [{ kind: 'caption', text: CAPTION[platform](title, description, hashtags) }];
  return parts.filter((part) => part.text.trim());
}
