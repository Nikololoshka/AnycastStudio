import type { PlatformCapabilities } from '../../domain/platform/types';
import type {
  PlatformDescriptor,
  PublicationDraft,
  ValidationResult,
} from '../PlatformDescriptor';

const CAPABILITIES: PlatformCapabilities = {
  label: 'YouTube',
  scheduling: 'native',
  title: true,
  description: true,
  hashtags: true,
  drafts: true,
  maxFileSize: 128 * 1024 ** 3,
  supportedMimeTypes: [
    'video/mp4',
    'video/quicktime',
    'video/x-msvideo',
    'video/x-ms-wmv',
    'video/x-flv',
    'video/3gpp',
    'video/webm',
    'video/mpeg',
  ],
};

export class YouTubeDescriptor implements PlatformDescriptor {
  getCapabilities(): PlatformCapabilities {
    return CAPABILITIES;
  }

  validate(draft: PublicationDraft): ValidationResult {
    const errors: string[] = [];

    if (!draft.title.trim()) {
      errors.push('titleRequired');
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
