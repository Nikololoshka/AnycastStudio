import { Channel, invoke } from '@tauri-apps/api/core';
import { fetch } from '@tauri-apps/plugin-http';
import type { PublicationError } from '../../domain/publication/types';
import type { UploadProgressCallback } from '../PlatformAdapter';

export interface MediaMetadata {
  caption: string;
  shareToFeed: boolean;
  thumbOffsetMs: number;
}

export interface UploadVideoResult {
  containerId: string;
}

interface UploadProgressEvent {
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
}

interface ContainerStatusResponse {
  status_code?: string;
  status?: string;
}

const POLL_INTERVALS_MS = [10_000, 30_000, 60_000, 120_000];
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const GRAPH_API_BASE = 'https://graph.facebook.com/v23.0';

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchContainerStatus(accessToken: string, containerId: string): Promise<string> {
  const url = new URL(`${GRAPH_API_BASE}/${containerId}`);
  url.searchParams.set('fields', 'status_code,status');
  url.searchParams.set('access_token', accessToken);

  const response = await fetch(url.toString());
  if (!response.ok) throw new Error(`failed to fetch container status: ${await response.text()}`);
  const body: ContainerStatusResponse = await response.json();
  return body.status_code ?? 'UNKNOWN';
}

async function pollContainerStatus(accessToken: string, containerId: string): Promise<void> {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  let attempt = 0;

  while (Date.now() < deadline) {
    const statusCode = await fetchContainerStatus(accessToken, containerId);

    if (statusCode === 'FINISHED') return;
    if (statusCode === 'ERROR' || statusCode === 'EXPIRED') {
      const error: PublicationError = {
        type: 'platform',
        message: `container status: ${statusCode}`,
      };
      throw error;
    }

    const interval = POLL_INTERVALS_MS[Math.min(attempt, POLL_INTERVALS_MS.length - 1)];
    await sleep(interval);
    attempt += 1;
  }

  const timeoutError: PublicationError = {
    type: 'platform',
    message: 'timed out waiting for Instagram container to finish processing',
  };
  throw timeoutError;
}

async function invokeUpload(
  uploadId: string,
  path: string,
  mimeType: string,
  accessToken: string,
  igUserId: string,
  metadata: MediaMetadata,
  onProgress: UploadProgressCallback,
): Promise<UploadVideoResult> {
  const channel = new Channel<UploadProgressEvent>();
  channel.onmessage = (event) => onProgress(event);

  const outcome = await invoke<{ containerId: string }>('upload_video_instagram', {
    params: {
      uploadId,
      path,
      mimeType,
      accessToken,
      igUserId,
      metadata,
    },
    onProgress: channel,
  });
  return outcome;
}

export async function uploadVideoToInstagram(
  uploadId: string,
  path: string,
  mimeType: string,
  getAccessToken: () => Promise<string>,
  igUserId: string,
  metadata: MediaMetadata,
  onProgress: UploadProgressCallback,
): Promise<UploadVideoResult> {
  let accessToken = await getAccessToken();

  let outcome: UploadVideoResult;
  try {
    outcome = await invokeUpload(
      uploadId,
      path,
      mimeType,
      accessToken,
      igUserId,
      metadata,
      onProgress,
    );
  } catch (error) {
    const publicationError = error as PublicationError;
    if (publicationError?.type !== 'authentication') throw error;

    accessToken = await getAccessToken();
    outcome = await invokeUpload(
      uploadId,
      path,
      mimeType,
      accessToken,
      igUserId,
      metadata,
      onProgress,
    );
  }

  await pollContainerStatus(await getAccessToken(), outcome.containerId);
  return outcome;
}

export function cancelInstagramUpload(uploadId: string): Promise<void> {
  return invoke('cancel_instagram_upload', { uploadId });
}
