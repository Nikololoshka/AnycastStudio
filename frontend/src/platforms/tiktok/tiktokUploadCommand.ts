import { Channel, invoke } from '@tauri-apps/api/core';
import { fetch } from '@tauri-apps/plugin-http';
import type { PublicationError } from '../../domain/publication/types';
import type { UploadProgressCallback } from '../PlatformAdapter';
import { createLogger } from '../../services/logs';

export interface PostInfo {
  title: string;
  privacyLevel:
    'SELF_ONLY' | 'PUBLIC_TO_EVERYONE' | 'MUTUAL_FOLLOW_FRIENDS' | 'FOLLOWER_OF_CREATOR';
  disableDuet: boolean;
  disableComment: boolean;
  disableStitch: boolean;
  isAigc: boolean;
  brandOrganicToggle: boolean;
  videoCoverTimestampMs?: number;
}

export interface UploadVideoResult {
  publishId: string;
}

interface UploadProgressEvent {
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
}

interface PublishStatusResponse {
  data?: { status?: string; fail_reason?: string };
  error?: { code?: string; message?: string };
}

const FAIL_REASON_MESSAGES: Record<string, string> = {
  file_format_check_failed: 'TikTok rejected the video format',
  duration_check_failed: "The video duration is outside TikTok's allowed range",
  frame_rate_check_failed: "The video frame rate is outside TikTok's allowed range",
  picture_size_check_failed: "The video resolution is outside TikTok's allowed range",
  video_pull_failed: 'TikTok could not read the uploaded video',
  publish_cancelled: 'The publish was cancelled on TikTok',
  spam_risk_too_many_posts: 'TikTok blocked the publish: daily post limit reached',
  spam_risk_user_banned_from_posting: 'TikTok blocked the publish: the account cannot post',
  spam_risk_text: 'TikTok flagged the caption as spam',
  spam_risk: 'TikTok flagged the publish as spam',
  user_cancel: 'The publish was cancelled by the user on TikTok',
  auth_removed: 'The TikTok authorization was revoked; reconnect the account',
  unaudited_client_can_only_post_to_private_accounts:
    'This TikTok app is unaudited and can only post to private accounts',
  privacy_level_check_failed: 'TikTok rejected the selected privacy level',
  internal:
    "TikTok's servers are temporarily unavailable; this is a retryable error on TikTok's side, try publishing again",
};

const logger = createLogger('tiktok');

function describeFailure(failReason: string | undefined): string {
  if (!failReason) return 'TikTok reported the publish failed';
  const description = FAIL_REASON_MESSAGES[failReason];
  return description ? `${description} (${failReason})` : `TikTok publish failed: ${failReason}`;
}

const POLL_INTERVALS_MS = [10_000, 30_000, 60_000, 120_000];
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
const STATUS_ENDPOINT = 'https://open.tiktokapis.com/v2/post/publish/status/fetch/';
const CREATOR_INFO_ENDPOINT = 'https://open.tiktokapis.com/v2/post/publish/creator_info/query/';

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

interface CreatorInfoResponse {
  data?: {
    creator_username?: string;
    privacy_level_options?: string[];
    max_video_post_duration_sec?: number;
    comment_disabled?: boolean;
    duet_disabled?: boolean;
    stitch_disabled?: boolean;
  };
  error?: { code?: string; message?: string };
}

async function queryCreatorInfo(accessToken: string): Promise<CreatorInfoResponse['data']> {
  const response = await fetch(CREATOR_INFO_ENDPOINT, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json; charset=UTF-8',
    },
  });
  const body: CreatorInfoResponse = await response.json();
  logger.debug(`creator info: ${JSON.stringify(body)}`);

  if (!response.ok || (body.error?.code && body.error.code !== 'ok')) {
    throw {
      type: 'platform',
      message: `TikTok rejected the creator info query: ${body.error?.code ?? response.status} ${body.error?.message ?? ''}`.trim(),
    } satisfies PublicationError;
  }
  return body.data;
}

function reconcilePostInfo(
  postInfo: PostInfo,
  creatorInfo: CreatorInfoResponse['data'],
  durationSeconds: number | undefined,
): PostInfo {
  const privacyOptions = creatorInfo?.privacy_level_options ?? [];
  if (privacyOptions.length > 0 && !privacyOptions.includes(postInfo.privacyLevel)) {
    throw {
      type: 'platform',
      message: `TikTok does not allow the privacy level ${postInfo.privacyLevel} for this account; allowed: ${privacyOptions.join(', ')}`,
    } satisfies PublicationError;
  }

  const maxDuration = creatorInfo?.max_video_post_duration_sec;
  if (maxDuration && durationSeconds && durationSeconds > maxDuration) {
    throw {
      type: 'platform',
      message: `The video is ${Math.round(durationSeconds)}s long, but this TikTok account may post at most ${maxDuration}s`,
    } satisfies PublicationError;
  }

  return {
    ...postInfo,
    disableComment: postInfo.disableComment || Boolean(creatorInfo?.comment_disabled),
    disableDuet: postInfo.disableDuet || Boolean(creatorInfo?.duet_disabled),
    disableStitch: postInfo.disableStitch || Boolean(creatorInfo?.stitch_disabled),
  };
}

async function fetchPublishStatus(
  accessToken: string,
  publishId: string,
): Promise<{ status: string; failReason?: string }> {
  const response = await fetch(STATUS_ENDPOINT, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json; charset=UTF-8',
    },
    body: JSON.stringify({ publish_id: publishId }),
  });
  if (!response.ok) throw new Error(`failed to fetch publish status: ${await response.text()}`);
  const body: PublishStatusResponse = await response.json();
  logger.debug(`publish status for ${publishId}: ${JSON.stringify(body)}`);
  return { status: body.data?.status ?? 'UNKNOWN', failReason: body.data?.fail_reason };
}

async function pollPublishStatus(accessToken: string, publishId: string): Promise<void> {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  let attempt = 0;

  while (Date.now() < deadline) {
    const { status, failReason } = await fetchPublishStatus(accessToken, publishId);

    if (status === 'PUBLISH_COMPLETE' || status === 'SEND_TO_USER_INBOX') return;
    if (status === 'FAILED') {
      throw {
        type: 'platform',
        message: describeFailure(failReason),
      } satisfies PublicationError;
    }

    const interval = POLL_INTERVALS_MS[Math.min(attempt, POLL_INTERVALS_MS.length - 1)];
    await sleep(interval);
    attempt += 1;
  }

  throw {
    type: 'platform',
    message: 'timed out waiting for TikTok to confirm the publish; check TikTok manually',
  } satisfies PublicationError;
}

async function invokeUpload(
  uploadId: string,
  path: string,
  mimeType: string,
  accessToken: string,
  postInfo: PostInfo,
  onProgress: UploadProgressCallback,
): Promise<UploadVideoResult> {
  const channel = new Channel<UploadProgressEvent>();
  channel.onmessage = (event) => onProgress(event);

  return invoke<UploadVideoResult>('upload_video_tiktok', {
    params: { uploadId, path, mimeType, accessToken, postInfo },
    onProgress: channel,
  });
}

export async function uploadVideoToTikTok(
  uploadId: string,
  path: string,
  mimeType: string,
  getAccessToken: () => Promise<string>,
  postInfo: PostInfo,
  onProgress: UploadProgressCallback,
  durationSeconds?: number,
): Promise<UploadVideoResult> {
  const accessToken = await getAccessToken();
  const creatorInfo = await queryCreatorInfo(accessToken);
  const reconciled = reconcilePostInfo(postInfo, creatorInfo, durationSeconds);

  const outcome = await (async () => {
    try {
      return await invokeUpload(uploadId, path, mimeType, accessToken, reconciled, onProgress);
    } catch (error) {
      const publicationError = error as PublicationError;
      if (publicationError?.type !== 'authentication') throw error;

      const refreshedToken = await getAccessToken();
      return invokeUpload(uploadId, path, mimeType, refreshedToken, reconciled, onProgress);
    }
  })();

  await pollPublishStatus(await getAccessToken(), outcome.publishId);
  return outcome;
}

export function cancelTikTokUpload(uploadId: string): Promise<void> {
  return invoke('cancel_tiktok_upload', { uploadId });
}
