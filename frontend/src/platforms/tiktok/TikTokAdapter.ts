import type { PlatformCapabilities } from '../../domain/platform/types';
import type {
  AdapterPublication,
  PlatformAdapter,
  PublishResult,
  UploadProgressCallback,
  UploadResult,
  ValidationResult,
} from '../PlatformAdapter';
import { TikTokAuth } from './TikTokAuth';
import { uploadVideoToTikTok, type PostInfo } from './tiktokUploadCommand';
import { toPublicationError } from '../../services/upload/errors';
import { tiktokSettingsOf } from './settings';

function captionOf(publication: AdapterPublication): string {
  const hashtags = publication.hashtags.map((tag) => `#${tag}`).join(' ');
  return [publication.description, hashtags].filter(Boolean).join('\n\n').trim();
}

function postInfoOf(publication: AdapterPublication): PostInfo {
  const settings = tiktokSettingsOf(publication.settings);
  const coverTimestampMs = Math.round(settings.coverFrameSeconds * 1000);

  return {
    title: captionOf(publication),
    privacyLevel: 'SELF_ONLY',
    disableDuet: settings.disableDuet,
    disableComment: settings.disableComment,
    disableStitch: settings.disableStitch,
    isAigc: settings.isAigc,
    brandOrganicToggle: settings.brandOrganicToggle,
    ...(coverTimestampMs > 0 ? { videoCoverTimestampMs: coverTimestampMs } : {}),
  };
}

export class TikTokAdapter implements PlatformAdapter {
  private readonly auth = new TikTokAuth();

  getCapabilities(): PlatformCapabilities {
    return {
      label: 'TikTok',
      scheduling: 'deferredUpload',
      title: false,
      description: true,
      hashtags: true,
      drafts: true,
      maxFileSize: 4 * 1024 ** 3,
      supportedMimeTypes: ['video/mp4', 'video/quicktime', 'video/webm'],
    };
  }

  validate(publication: AdapterPublication): ValidationResult {
    const errors: string[] = [];
    const capabilities = this.getCapabilities();

    if (capabilities.maxFileSize && publication.video.size > capabilities.maxFileSize) {
      errors.push(`File exceeds TikTok's maximum size of ${capabilities.maxFileSize} bytes`);
    }
    if (
      capabilities.supportedMimeTypes &&
      !capabilities.supportedMimeTypes.includes(publication.video.mimeType)
    ) {
      errors.push(`Unsupported file type: ${publication.video.mimeType}`);
    }

    return { valid: errors.length === 0, errors };
  }

  async upload(
    publication: AdapterPublication,
    onProgress: UploadProgressCallback,
  ): Promise<UploadResult> {
    try {
      const uploadId = crypto.randomUUID();

      const result = await uploadVideoToTikTok(
        uploadId,
        publication.video.path,
        publication.video.mimeType,
        () => this.auth.getValidAccessToken(publication.accountId),
        postInfoOf(publication),
        onProgress,
        publication.video.duration,
      );
      return { success: true, videoId: result.publishId };
    } catch (error) {
      return { success: false, error: toPublicationError(error) };
    }
  }

  async publish(_publication: AdapterPublication): Promise<PublishResult> {
    return { success: true };
  }
}
