import { fetch } from '@tauri-apps/plugin-http';
import type { PlatformCapabilities } from '../../domain/platform/types';
import type {
  AdapterPublication,
  PlatformAdapter,
  PublishResult,
  UploadProgressCallback,
  UploadResult,
  ValidationResult,
} from '../PlatformAdapter';
import { InstagramAuth } from './InstagramAuth';
import { uploadVideoToInstagram, type MediaMetadata } from './instagramUploadCommand';
import { toPublicationError } from '../../services/upload/errors';
import { instagramSettingsOf } from './settings';

const MEDIA_PUBLISH_ENDPOINT_BASE = 'https://graph.facebook.com/v23.0';

function igUserIdOf(publication: AdapterPublication): string {
  return publication.accountId.split(':')[1];
}

function mediaMetadataOf(publication: AdapterPublication): MediaMetadata {
  const hashtags = publication.hashtags.map((tag) => `#${tag}`).join(' ');
  const caption = [publication.description, hashtags].filter(Boolean).join('\n\n').trim();

  const settings = instagramSettingsOf(publication.settings);

  return {
    caption,
    shareToFeed: settings.shareToFeed,
    thumbOffsetMs: Math.round(settings.coverFrameSeconds * 1000),
  };
}

export class InstagramAdapter implements PlatformAdapter {
  private readonly auth = new InstagramAuth();

  getCapabilities(): PlatformCapabilities {
    return {
      label: 'Instagram',
      scheduling: 'stagedPublish',
      stagedMediaTtlMs: 24 * 60 * 60 * 1000,
      title: false,
      description: true,
      hashtags: true,
      drafts: false,
      maxFileSize: 1024 ** 3,
      supportedMimeTypes: ['video/mp4', 'video/quicktime'],
    };
  }

  validate(publication: AdapterPublication): ValidationResult {
    const errors: string[] = [];
    const capabilities = this.getCapabilities();

    if (capabilities.maxFileSize && publication.video.size > capabilities.maxFileSize) {
      errors.push(`File exceeds Instagram's maximum size of ${capabilities.maxFileSize} bytes`);
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

      const result = await uploadVideoToInstagram(
        uploadId,
        publication.video.path,
        publication.video.mimeType,
        () => this.auth.getValidAccessToken(publication.accountId),
        igUserIdOf(publication),
        mediaMetadataOf(publication),
        onProgress,
      );
      return { success: true, videoId: result.containerId };
    } catch (error) {
      return { success: false, error: toPublicationError(error) };
    }
  }

  async publish(publication: AdapterPublication): Promise<PublishResult> {
    if (!publication.uploadedVideoId) {
      return {
        success: false,
        error: { type: 'unknown', message: 'no uploaded container id to publish' },
      };
    }

    const igUserId = igUserIdOf(publication);
    const accessToken = await this.auth.getValidAccessToken(publication.accountId);

    const publishUrl = new URL(`${MEDIA_PUBLISH_ENDPOINT_BASE}/${igUserId}/media_publish`);
    publishUrl.searchParams.set('creation_id', publication.uploadedVideoId);
    publishUrl.searchParams.set('access_token', accessToken);

    const response = await fetch(publishUrl.toString(), { method: 'POST' });
    if (!response.ok) {
      return { success: false, error: { type: 'platform', message: await response.text() } };
    }
    const body: { id?: string } = await response.json();
    if (!body.id) {
      return {
        success: false,
        error: { type: 'platform', message: 'media_publish returned no id' },
      };
    }

    const publishedUrl = await this.fetchPermalink(accessToken, body.id);
    return { success: true, publishedUrl };
  }

  private async fetchPermalink(accessToken: string, mediaId: string): Promise<string | undefined> {
    try {
      const permalinkUrl = new URL(`${MEDIA_PUBLISH_ENDPOINT_BASE}/${mediaId}`);
      permalinkUrl.searchParams.set('fields', 'permalink');
      permalinkUrl.searchParams.set('access_token', accessToken);

      const response = await fetch(permalinkUrl.toString());
      if (!response.ok) return undefined;
      const body: { permalink?: string } = await response.json();
      return body.permalink;
    } catch {
      return undefined;
    }
  }
}
