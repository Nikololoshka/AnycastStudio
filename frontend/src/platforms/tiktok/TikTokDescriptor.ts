import type { PlatformCapabilities } from '../../domain/platform/types';
import type { PlatformDescriptor, PublicationDraft, ValidationResult } from '../PlatformDescriptor';
import {
  TIKTOK_MAX_CAPTION_LENGTH,
  tiktokCaptionOf,
  tiktokSettingErrors,
  tiktokSettingsOf,
} from './settings';

const CAPABILITIES: PlatformCapabilities = {
  label: 'TikTok',
  scheduling: 'deferredUpload',
  title: true,
  description: true,
  hashtags: true,
  drafts: false,
  maxFileSize: 4 * 1024 ** 3,
  supportedMimeTypes: ['video/mp4', 'video/quicktime', 'video/webm'],
};

export class TikTokDescriptor implements PlatformDescriptor {
  getCapabilities(): PlatformCapabilities {
    return CAPABILITIES;
  }

  validate(draft: PublicationDraft): ValidationResult {
    const errors = tiktokSettingErrors(tiktokSettingsOf(draft.settings));

    if (
      tiktokCaptionOf(draft.title, draft.description, draft.hashtags).length >
      TIKTOK_MAX_CAPTION_LENGTH
    ) {
      errors.push('captionTooLong');
    }
    if (!draft.video) {
      errors.push('videoRequired');
    } else {
      if (CAPABILITIES.maxFileSize && draft.video.size > CAPABILITIES.maxFileSize) {
        errors.push('fileTooLarge');
      }
      if (
        CAPABILITIES.supportedMimeTypes &&
        !CAPABILITIES.supportedMimeTypes.includes(draft.video.mimeType)
      ) {
        errors.push('unsupportedType');
      }
    }

    return { valid: errors.length === 0, errors };
  }
}
