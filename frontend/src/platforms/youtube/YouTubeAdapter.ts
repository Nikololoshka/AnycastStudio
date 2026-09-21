import type {
  PlatformCapabilities,
  PlatformSettings,
  SchedulingMode,
} from '../../domain/platform/types';
import type {
  AdapterPublication,
  PlatformAdapter,
  PublishResult,
  ScheduleResult,
  UploadProgressCallback,
  UploadResult,
  ValidationResult,
} from '../PlatformAdapter';
import { YouTubeAuth } from './YouTubeAuth';
import { uploadVideoToYouTube } from './youtubeUploadCommand';
import { toPublicationError } from '../../services/upload/errors';
import { youtubeSettingsOf, type YouTubeSettings } from './settings';

const VIDEOS_ENDPOINT = 'https://www.googleapis.com/youtube/v3/videos?part=status';
const MAX_DESCRIPTION_HASHTAGS = 15;

function descriptionOf(publication: AdapterPublication, settings: YouTubeSettings): string {
  if (!settings.hashtagsInDescription || publication.hashtags.length === 0) {
    return publication.description;
  }
  const hashtags = publication.hashtags
    .slice(0, MAX_DESCRIPTION_HASHTAGS)
    .map((tag) => `#${tag}`)
    .join(' ');
  return [publication.description, hashtags].filter(Boolean).join('\n\n');
}

function statusFieldsOf(settings: YouTubeSettings) {
  return {
    license: settings.license,
    embeddable: settings.embeddable,
    publicStatsViewable: settings.publicStatsViewable,
    selfDeclaredMadeForKids: settings.madeForKids,
    containsSyntheticMedia: settings.containsSyntheticMedia,
  };
}

export class YouTubeAdapter implements PlatformAdapter {
  private readonly auth = new YouTubeAuth();

  getCapabilities(): PlatformCapabilities {
    return {
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
  }

  getSchedulingMode(settings: PlatformSettings): SchedulingMode {
    return youtubeSettingsOf(settings).privacyStatus === 'public' ? 'native' : 'stagedPublish';
  }

  validate(publication: AdapterPublication): ValidationResult {
    const errors: string[] = [];
    const capabilities = this.getCapabilities();

    if (!publication.title.trim()) {
      errors.push('Title is required for YouTube');
    }
    if (capabilities.maxFileSize && publication.video.size > capabilities.maxFileSize) {
      errors.push(`File exceeds YouTube's maximum size of ${capabilities.maxFileSize} bytes`);
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
      const settings = youtubeSettingsOf(publication.settings);

      const result = await uploadVideoToYouTube(
        uploadId,
        publication.video.path,
        publication.video.mimeType,
        () => this.auth.getValidAccessToken(publication.accountId),
        {
          title: publication.title,
          description: descriptionOf(publication, settings),
          tags: publication.hashtags,
          privacyStatus: publication.scheduledAt ? 'private' : settings.privacyStatus,
          categoryId: settings.categoryId,
          license: settings.license,
          embeddable: settings.embeddable,
          publicStatsViewable: settings.publicStatsViewable,
          madeForKids: settings.madeForKids,
          containsSyntheticMedia: settings.containsSyntheticMedia,
          notifySubscribers: settings.notifySubscribers,
        },
        onProgress,
      );
      return { success: true, videoId: result.videoId };
    } catch (error) {
      return { success: false, error: toPublicationError(error) };
    }
  }

  async publish(publication: AdapterPublication): Promise<PublishResult> {
    if (!publication.uploadedVideoId) {
      return {
        success: false,
        error: { type: 'unknown', message: 'no uploaded video id to publish' },
      };
    }
    const settings = youtubeSettingsOf(publication.settings);
    const accessToken = await this.auth.getValidAccessToken(publication.accountId);
    const response = await fetch(VIDEOS_ENDPOINT, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json; charset=UTF-8',
      },
      body: JSON.stringify({
        id: publication.uploadedVideoId,
        status: { privacyStatus: settings.privacyStatus, ...statusFieldsOf(settings) },
      }),
    });
    if (!response.ok) {
      return { success: false, error: { type: 'platform', message: await response.text() } };
    }
    return {
      success: true,
      publishedUrl: `https://youtu.be/${publication.uploadedVideoId}`,
    };
  }

  async schedule(publication: AdapterPublication): Promise<ScheduleResult> {
    if (!publication.uploadedVideoId || !publication.scheduledAt) {
      return {
        success: false,
        scheduledAt: publication.scheduledAt ?? '',
        error: { type: 'unknown', message: 'missing uploaded video id or scheduledAt' },
      };
    }
    const accessToken = await this.auth.getValidAccessToken(publication.accountId);
    const response = await fetch(VIDEOS_ENDPOINT, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json; charset=UTF-8',
      },
      body: JSON.stringify({
        id: publication.uploadedVideoId,
        status: {
          privacyStatus: 'private',
          publishAt: publication.scheduledAt,
          ...statusFieldsOf(youtubeSettingsOf(publication.settings)),
        },
      }),
    });
    if (!response.ok) {
      return {
        success: false,
        scheduledAt: publication.scheduledAt,
        error: { type: 'platform', message: await response.text() },
      };
    }
    return { success: true, scheduledAt: publication.scheduledAt };
  }
}
