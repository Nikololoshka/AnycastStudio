import type { PlatformSettings } from '../../domain/platform/types';
import type { PlatformSelectOption } from '../selectOptions';

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

export const X_REPLY_AUDIENCE_OPTIONS: PlatformSelectOption<XReplyAudience>[] = [
  { value: 'everyone', labelKey: 'x.replyAudience.everyone' },
  { value: 'following', labelKey: 'x.replyAudience.following' },
  { value: 'mentionedUsers', labelKey: 'x.replyAudience.mentionedUsers' },
  { value: 'subscribers', labelKey: 'x.replyAudience.subscribers' },
  { value: 'verified', labelKey: 'x.replyAudience.verified' },
];

export function xSettingsOf(settings: PlatformSettings): XSettings {
  const replyAudience = X_REPLY_AUDIENCE_OPTIONS.some(
    (option) => option.value === settings.replyAudience,
  )
    ? (settings.replyAudience as XReplyAudience)
    : X_DEFAULT_SETTINGS.replyAudience;

  return {
    replyAudience,
    madeWithAi: Boolean(settings.madeWithAi ?? X_DEFAULT_SETTINGS.madeWithAi),
    paidPartnership: Boolean(settings.paidPartnership ?? X_DEFAULT_SETTINGS.paidPartnership),
    superFollowersOnly: Boolean(
      settings.superFollowersOnly ?? X_DEFAULT_SETTINGS.superFollowersOnly,
    ),
  };
}
