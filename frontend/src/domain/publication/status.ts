import type { PublicationStatus } from './types';

/** Statuses where no percentage is meaningful, so the bar should just move. */
export const INDETERMINATE_STATUSES: PublicationStatus[] = [
  'queued',
  'validating',
  'processing',
  'publishing',
];

export const ACTIVE_STATUSES: PublicationStatus[] = [...INDETERMINATE_STATUSES, 'uploading'];

export function isActiveStatus(status: PublicationStatus): boolean {
  return ACTIVE_STATUSES.includes(status);
}
