export interface Quota {
  maxStorageBytes: number;
  maxMediaAssetBytes: number;
  maxConcurrentUploads: number;
  maxPublicationsPerDay: number;
}

export interface CurrentUser {
  id: number;
  email: string;
  displayName: string;
  name: string;
  isStaff: boolean;
  locale: string;
  timezone: string;
  theme: string;
  mediaRetentionDays: 7 | 30 | 90 | null;
  defaultPlatforms: string[];
  platformDefaults: Record<string, Record<string, unknown>>;
  quota: Quota;
}

export interface ApiError {
  field: string;
  message: string;
}

/** Every endpoint answers with a `status` string; the HTTP code follows from it. */
export interface ApiEnvelope {
  status: string;
  message?: string;
  errors?: ApiError[];
}
