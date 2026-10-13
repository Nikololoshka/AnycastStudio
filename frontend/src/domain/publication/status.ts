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

const SETTLED_PRIORITY: PublicationStatus[] = ['failed', 'scheduled', 'completed', 'cancelled'];

export function overallStatus(statuses: PublicationStatus[]): PublicationStatus {
  return (
    statuses.find(isActiveStatus) ??
    SETTLED_PRIORITY.find((status) => statuses.includes(status)) ??
    'queued'
  );
}
