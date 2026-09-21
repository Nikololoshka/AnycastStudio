export type Platform = 'youtube' | 'x' | 'instagram' | 'tiktok';

export type SchedulingMode = 'native' | 'stagedPublish' | 'deferredUpload' | 'unsupported';

export interface PlatformCapabilities {
  label: string;

  scheduling: SchedulingMode;

  stagedMediaTtlMs?: number;

  title: boolean;
  description: boolean;
  hashtags: boolean;

  drafts: boolean;

  maxFileSize?: number;
  supportedMimeTypes?: string[];
}

export type PlatformSettings = Record<string, unknown>;

export interface ConnectedAccount {
  id: string;
  platform: Platform;
  displayName: string;
  avatarUrl?: string;
}
