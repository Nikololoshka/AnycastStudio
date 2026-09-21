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
import { XAuth } from './XAuth';
import { uploadVideoToX } from './xUploadCommand';
import { toPublicationError } from '../../services/upload/errors';
import { xSettingsOf } from './settings';

const TWEETS_ENDPOINT = 'https://api.x.com/2/tweets';
const TWEET_TEXT_LIMIT = 280;

function tweetTextOf(publication: AdapterPublication): string {
  const hashtags = publication.hashtags.map((tag) => `#${tag}`).join(' ');
  return [publication.description, hashtags].filter(Boolean).join(' ').trim();
}

function tweetBodyOf(publication: AdapterPublication): Record<string, unknown> {
  const settings = xSettingsOf(publication.settings);

  return {
    text: tweetTextOf(publication),
    media: { media_ids: [publication.uploadedVideoId] },
    ...(settings.replyAudience === 'everyone' ? {} : { reply_settings: settings.replyAudience }),
    made_with_ai: settings.madeWithAi,
    paid_partnership: settings.paidPartnership,
    for_super_followers_only: settings.superFollowersOnly,
  };
}

export class XAdapter implements PlatformAdapter {
  private readonly auth = new XAuth();

  getCapabilities(): PlatformCapabilities {
    return {
      label: 'X',
      scheduling: 'stagedPublish',
      stagedMediaTtlMs: 24 * 60 * 60 * 1000,
      title: false,
      description: true,
      hashtags: true,
      drafts: false,
      maxFileSize: 512 * 1024 ** 2,
      supportedMimeTypes: ['video/mp4', 'video/quicktime'],
    };
  }

  validate(publication: AdapterPublication): ValidationResult {
    const errors: string[] = [];
    const capabilities = this.getCapabilities();

    if (capabilities.maxFileSize && publication.video.size > capabilities.maxFileSize) {
      errors.push(`File exceeds X's maximum size of ${capabilities.maxFileSize} bytes`);
    }
    if (
      capabilities.supportedMimeTypes &&
      !capabilities.supportedMimeTypes.includes(publication.video.mimeType)
    ) {
      errors.push(`Unsupported file type: ${publication.video.mimeType}`);
    }
    if (tweetTextOf(publication).length > TWEET_TEXT_LIMIT) {
      errors.push(`Tweet text exceeds X's ${TWEET_TEXT_LIMIT} character limit`);
    }

    return { valid: errors.length === 0, errors };
  }

  async upload(
    publication: AdapterPublication,
    onProgress: UploadProgressCallback,
  ): Promise<UploadResult> {
    try {
      const uploadId = crypto.randomUUID();

      const result = await uploadVideoToX(
        uploadId,
        publication.video.path,
        publication.video.mimeType,
        () => this.auth.getValidAccessToken(publication.accountId),
        onProgress,
      );
      return { success: true, videoId: result.mediaId };
    } catch (error) {
      return { success: false, error: toPublicationError(error) };
    }
  }

  async publish(publication: AdapterPublication): Promise<PublishResult> {
    if (!publication.uploadedVideoId) {
      return {
        success: false,
        error: { type: 'unknown', message: 'no uploaded media id to publish' },
      };
    }
    const accessToken = await this.auth.getValidAccessToken(publication.accountId);
    const response = await fetch(TWEETS_ENDPOINT, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(tweetBodyOf(publication)),
    });
    if (!response.ok) {
      return { success: false, error: { type: 'platform', message: await response.text() } };
    }
    const body = await response.json();
    const tweetId = body.data?.id;
    return {
      success: true,
      publishedUrl: tweetId ? `https://x.com/i/web/status/${tweetId}` : undefined,
    };
  }
}
