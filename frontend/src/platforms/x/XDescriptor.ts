import type { PlatformCapabilities } from '../../domain/platform/types';
import type { PlatformDescriptor, PublicationDraft, ValidationResult } from '../PlatformDescriptor';
import { xCaptionErrors, xCaptionOf, xDurationErrors } from './settings';

const CAPABILITIES: PlatformCapabilities = {
  label: 'X',
  scheduling: 'deferredUpload',
  title: true,
  description: true,
  hashtags: true,
  drafts: false,
  maxFileSize: 512 * 1024 ** 2,
  supportedMimeTypes: ['video/mp4', 'video/quicktime'],
};

export class XDescriptor implements PlatformDescriptor {
  getCapabilities(): PlatformCapabilities {
    return CAPABILITIES;
  }

  validate(draft: PublicationDraft): ValidationResult {
    const errors = xCaptionErrors(xCaptionOf(draft.title, draft.description, draft.hashtags));

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
      errors.push(...xDurationErrors(draft.video.duration));
    }

    return { valid: errors.length === 0, errors };
  }
}
