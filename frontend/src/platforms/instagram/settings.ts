import type { PlatformSettings } from '../../domain/platform/types';
import type { DraftError } from '../PlatformDescriptor';

export type InstagramSettings = {
  shareToFeed: boolean;
  coverFrameSeconds: number;
};

export const INSTAGRAM_DEFAULT_SETTINGS: InstagramSettings = {
  shareToFeed: true,
  coverFrameSeconds: 0,
};

export const INSTAGRAM_MAX_CAPTION_LENGTH = 2200;
export const INSTAGRAM_MAX_HASHTAGS = 30;
export const INSTAGRAM_MIN_DURATION_SECONDS = 3;
export const INSTAGRAM_MAX_DURATION_SECONDS = 15 * 60;

const HASHTAG = /(?<![\p{L}\p{N}_#])#[\p{L}\p{N}_]+/gu;

function secondsOf(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0;
}

export function instagramSettingsOf(settings: PlatformSettings): InstagramSettings {
  return {
    shareToFeed: typeof settings.shareToFeed === 'boolean' ? settings.shareToFeed : true,
    coverFrameSeconds: secondsOf(settings.coverFrameSeconds),
  };
}

export function instagramCaptionOf(title: string, description: string, hashtags: string[]): string {
  const tags = hashtags.map((tag) => `#${tag}`).join(' ');
  return [title.trim(), description.trim(), tags].filter(Boolean).join('\n\n');
}

export function hashtagCountOf(caption: string): number {
  return caption.match(HASHTAG)?.length ?? 0;
}

export function instagramCaptionErrors(caption: string): DraftError[] {
  const errors: DraftError[] = [];
  if (caption.length > INSTAGRAM_MAX_CAPTION_LENGTH) {
    errors.push('captionTooLong');
  }
  if (hashtagCountOf(caption) > INSTAGRAM_MAX_HASHTAGS) {
    errors.push('tooManyHashtags');
  }
  return errors;
}

export function instagramDurationErrors(duration: number | undefined): DraftError[] {
  if (!duration) {
    return [];
  }
  if (duration < INSTAGRAM_MIN_DURATION_SECONDS) {
    return ['videoTooShort'];
  }
  if (duration > INSTAGRAM_MAX_DURATION_SECONDS) {
    return ['videoTooLong'];
  }
  return [];
}
