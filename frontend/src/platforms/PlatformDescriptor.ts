import type { PlatformCapabilities, PlatformSettings } from '../domain/platform/types';
import type { VideoFile } from '../domain/video/types';

export type DraftError =
  | 'titleRequired'
  | 'videoRequired'
  | 'fileTooLarge'
  | 'unsupportedType'
  | 'captionTooLong'
  | 'privacyRequired'
  | 'commercialContentUnspecified'
  | 'brandedContentCannotBePrivate'
  | 'tooManyHashtags'
  | 'videoTooShort'
  | 'videoTooLong';

export interface ValidationResult {
  valid: boolean;
  errors: DraftError[];
}

/** What the composer knows about a publication before it is sent to the server. */
export interface PublicationDraft {
  video?: VideoFile;
  title: string;
  description: string;
  hashtags: string[];
  publishAt?: string;
  settings: PlatformSettings;
}

/**
 * A platform as the browser sees it: what it supports and what it will refuse.
 *
 * Uploading, publishing and scheduling happen on the server, so they are not
 * here. Validation is duplicated on purpose — this copy exists to tell the
 * person what is wrong before they wait for an upload, and the server's copy
 * is the one that decides.
 */
export interface PlatformDescriptor {
  getCapabilities(): PlatformCapabilities;
  validate(draft: PublicationDraft): ValidationResult;
}
