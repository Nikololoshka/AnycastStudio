import { Channel, invoke } from '@tauri-apps/api/core';
import { fetch } from '@tauri-apps/plugin-http';
import type { PublicationError } from '../../domain/publication/types';
import type { UploadProgressCallback } from '../PlatformAdapter';

export interface UploadVideoResult {
  mediaId: string;
}

interface UploadProgressEvent {
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
}

interface MediaStatusResponse {
  data?: { processing_info?: { state?: string; check_after_secs?: number } };
}

const POLL_INTERVALS_MS = [5_000, 10_000, 30_000, 60_000];
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const STATUS_ENDPOINT = 'https://api.x.com/2/media/upload';

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchProcessingState(accessToken: string, mediaId: string): Promise<string> {
  const url = new URL(STATUS_ENDPOINT);
  url.searchParams.set('command', 'STATUS');
  url.searchParams.set('media_id', mediaId);

  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) throw new Error(`failed to fetch media status: ${await response.text()}`);
  const body: MediaStatusResponse = await response.json();
  return body.data?.processing_info?.state ?? 'succeeded';
}

async function pollProcessingStatus(accessToken: string, mediaId: string): Promise<void> {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  let attempt = 0;

  while (Date.now() < deadline) {
    const state = await fetchProcessingState(accessToken, mediaId);

    if (state === 'succeeded') return;
    if (state === 'failed') {
      throw {
        type: 'platform',
        message: 'X reported the media processing failed',
      } satisfies PublicationError;
    }

    const interval = POLL_INTERVALS_MS[Math.min(attempt, POLL_INTERVALS_MS.length - 1)];
    await sleep(interval);
    attempt += 1;
  }

  throw {
    type: 'platform',
    message: 'timed out waiting for X to finish processing the media; check X manually',
  } satisfies PublicationError;
}

async function invokeUpload(
  uploadId: string,
  path: string,
  mimeType: string,
  accessToken: string,
  onProgress: UploadProgressCallback,
): Promise<UploadVideoResult> {
  const channel = new Channel<UploadProgressEvent>();
  channel.onmessage = (event) => onProgress(event);

  return invoke<UploadVideoResult>('upload_video_x', {
    params: { uploadId, path, mimeType, accessToken },
    onProgress: channel,
  });
}

export async function uploadVideoToX(
  uploadId: string,
  path: string,
  mimeType: string,
  getAccessToken: () => Promise<string>,
  onProgress: UploadProgressCallback,
): Promise<UploadVideoResult> {
  const accessToken = await getAccessToken();

  const outcome = await (async () => {
    try {
      return await invokeUpload(uploadId, path, mimeType, accessToken, onProgress);
    } catch (error) {
      const publicationError = error as PublicationError;
      if (publicationError?.type !== 'authentication') throw error;

      const refreshedToken = await getAccessToken();
      return invokeUpload(uploadId, path, mimeType, refreshedToken, onProgress);
    }
  })();

  await pollProcessingStatus(await getAccessToken(), outcome.mediaId);
  return outcome;
}

export function cancelXUpload(uploadId: string): Promise<void> {
  return invoke('cancel_x_upload', { uploadId });
}
