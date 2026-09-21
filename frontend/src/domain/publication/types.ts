import type { Platform, PlatformSettings } from '../platform/types';
import type { VideoFile } from '../video/types';

export type PublicationStatus =
  | 'idle'
  | 'validating'
  | 'preparing'
  | 'uploading'
  | 'processing'
  | 'publishing'
  | 'scheduled'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type ErrorType =
  | 'network'
  | 'authentication'
  | 'authorization'
  | 'validation'
  | 'rate_limit'
  | 'platform'
  | 'file'
  | 'unknown';

export interface PublicationError {
  type: ErrorType;
  message: string;
  details?: string;
}

export interface PlatformPublication {
  platform: Platform;

  enabled: boolean;

  settings: PlatformSettings;

  status: PublicationStatus;

  progress: number;

  error?: PublicationError;

  uploadedVideoId?: string;

  scheduledAt?: string;
}

export interface UploadProgress {
  platform: Platform;

  status: PublicationStatus;

  uploadedBytes?: number;
  totalBytes?: number;

  percent?: number;
}

export interface Publication {
  id: string;

  video: VideoFile;

  title: string;
  description: string;
  hashtags: string[];

  scheduledAt?: string;

  platforms: PlatformPublication[];
}
