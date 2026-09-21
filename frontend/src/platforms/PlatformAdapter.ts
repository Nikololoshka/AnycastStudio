import type {
  PlatformCapabilities,
  PlatformSettings,
  SchedulingMode,
} from '../domain/platform/types';
import type { PlatformPublication, PublicationError } from '../domain/publication/types';
import type { VideoFile } from '../domain/video/types';

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

export interface UploadResult {
  success: boolean;
  videoId?: string;
  error?: PublicationError;
}

export interface PublishResult {
  success: boolean;
  publishedUrl?: string;
  error?: PublicationError;
}

export interface ScheduleResult {
  success: boolean;
  scheduledAt: string;
  error?: PublicationError;
}

export interface AdapterPublication extends PlatformPublication {
  accountId: string;
  video: VideoFile;
  title: string;
  description: string;
  hashtags: string[];
  scheduledAt?: string;
  uploadedVideoId?: string;
}

export type UploadProgressCallback = (progress: {
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
}) => void;

export interface PlatformAdapter {
  getCapabilities(): PlatformCapabilities;

  getSchedulingMode?(settings: PlatformSettings): SchedulingMode;

  validate(publication: AdapterPublication): ValidationResult;

  upload(
    publication: AdapterPublication,
    onProgress: UploadProgressCallback,
  ): Promise<UploadResult>;

  publish(publication: AdapterPublication): Promise<PublishResult>;

  schedule?(publication: AdapterPublication): Promise<ScheduleResult>;
}
