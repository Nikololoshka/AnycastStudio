import { Channel, invoke } from '@tauri-apps/api/core';
import type { PublicationError } from '../../domain/publication/types';
import type { UploadProgressCallback } from '../PlatformAdapter';
import type { YouTubeLicense, YouTubePrivacy } from './settings';

export interface VideoMetadata {
  title: string;
  description: string;
  tags: string[];
  privacyStatus: YouTubePrivacy;
  categoryId: string;
  license: YouTubeLicense;
  embeddable: boolean;
  publicStatsViewable: boolean;
  madeForKids: boolean;
  containsSyntheticMedia: boolean;
  notifySubscribers: boolean;
}

export interface UploadVideoResult {
  videoId: string;
}

interface ResumeState {
  sessionUri: string;
  resumeOffset: number;
}

interface UploadProgressEvent {
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
}

function parseResumeState(details: string | undefined): ResumeState | undefined {
  if (!details) return undefined;
  try {
    return JSON.parse(details) as ResumeState;
  } catch {
    return undefined;
  }
}

async function invokeUpload(
  uploadId: string,
  path: string,
  mimeType: string,
  accessToken: string,
  metadata: VideoMetadata,
  onProgress: UploadProgressCallback,
  resume?: ResumeState,
): Promise<UploadVideoResult> {
  const channel = new Channel<UploadProgressEvent>();
  channel.onmessage = (event) => onProgress(event);

  const outcome = await invoke<{ videoId: string }>('upload_video_youtube', {
    params: {
      uploadId,
      path,
      mimeType,
      accessToken,
      metadata,
      sessionUri: resume?.sessionUri,
      resumeOffset: resume?.resumeOffset,
    },
    onProgress: channel,
  });
  return outcome;
}

export async function uploadVideoToYouTube(
  uploadId: string,
  path: string,
  mimeType: string,
  getAccessToken: () => Promise<string>,
  metadata: VideoMetadata,
  onProgress: UploadProgressCallback,
): Promise<UploadVideoResult> {
  const accessToken = await getAccessToken();

  try {
    return await invokeUpload(uploadId, path, mimeType, accessToken, metadata, onProgress);
  } catch (error) {
    const publicationError = error as PublicationError;
    const resume = parseResumeState(publicationError?.details);
    if (publicationError?.type !== 'authentication' || !resume) throw error;

    const refreshedToken = await getAccessToken();
    return invokeUpload(uploadId, path, mimeType, refreshedToken, metadata, onProgress, resume);
  }
}

export function cancelYouTubeUpload(uploadId: string): Promise<void> {
  return invoke('cancel_youtube_upload', { uploadId });
}
