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
