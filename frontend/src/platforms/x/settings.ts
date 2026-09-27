import type { PlatformSettings } from '../../domain/platform/types';
import type { DraftError } from '../PlatformDescriptor';
import { oneOf, type PlatformSelectOption } from '../selectOptions';

export type XReplyAudience =
  'everyone' | 'following' | 'mentionedUsers' | 'subscribers' | 'verified';

export type XSettings = {
  replyAudience: XReplyAudience;
  madeWithAi: boolean;
  paidPartnership: boolean;
  superFollowersOnly: boolean;
};

export const X_DEFAULT_SETTINGS: XSettings = {
  replyAudience: 'everyone',
  madeWithAi: false,
  paidPartnership: false,
  superFollowersOnly: false,
};

export const X_MAX_TEXT_LENGTH = 280;
export const X_MIN_DURATION_SECONDS = 0.5;
export const X_MAX_DURATION_SECONDS = 140;

export const X_REPLY_AUDIENCE_OPTIONS: PlatformSelectOption<XReplyAudience>[] = [
  { value: 'everyone', labelKey: 'x.replyAudience.everyone' },
  { value: 'following', labelKey: 'x.replyAudience.following' },
  { value: 'mentionedUsers', labelKey: 'x.replyAudience.mentionedUsers' },
  { value: 'subscribers', labelKey: 'x.replyAudience.subscribers' },
  { value: 'verified', labelKey: 'x.replyAudience.verified' },
];

function flagOf(value: unknown): boolean {
  return typeof value === 'boolean' ? value : false;
}

export function xSettingsOf(settings: PlatformSettings): XSettings {
  return {
    replyAudience: oneOf(settings.replyAudience, X_REPLY_AUDIENCE_OPTIONS, 'everyone'),
    madeWithAi: flagOf(settings.madeWithAi),
    paidPartnership: flagOf(settings.paidPartnership),
    superFollowersOnly: flagOf(settings.superFollowersOnly),
  };
}

export function xCaptionOf(title: string, description: string, hashtags: string[]): string {
  const tags = hashtags.map((tag) => `#${tag}`).join(' ');
  return [title.trim(), description.trim(), tags].filter(Boolean).join('\n\n');
}

export function xCaptionErrors(caption: string): DraftError[] {
  return caption.length > X_MAX_TEXT_LENGTH ? ['captionTooLong'] : [];
}

export function xDurationErrors(duration: number | undefined): DraftError[] {
  if (!duration) {
    return [];
  }
  if (duration < X_MIN_DURATION_SECONDS) {
    return ['videoTooShort'];
  }
  if (duration > X_MAX_DURATION_SECONDS) {
    return ['videoTooLong'];
  }
  return [];
}
