/** The wire contract with the server; see backend/publishing/models.py. */
export type PublicationStatus =
  | 'queued'
  | 'validating'
  | 'uploading'
  | 'processing'
  | 'publishing'
  | 'scheduled'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type PlatformFailure =
  | 'network'
  | 'rate_limited'
  | 'token_rejected'
  | 'grant_revoked'
  | 'scope_missing'
  | 'misconfigured'
  | 'invalid'
  | 'file_rejected'
  | 'media_missing'
  | 'refused'
  | 'unconfirmed'
  | 'unexpected';

export interface PublicationError {
  failure: PlatformFailure;
  message: string;
  details?: string;
}
