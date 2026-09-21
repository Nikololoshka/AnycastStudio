import type { PublicationStatus } from './types';

export const INDETERMINATE_STATUSES: PublicationStatus[] = [
  'validating',
  'preparing',
  'processing',
  'publishing',
];

export const ACTIVE_STATUSES: PublicationStatus[] = [...INDETERMINATE_STATUSES, 'uploading'];

export function isActiveStatus(status: PublicationStatus): boolean {
  return ACTIVE_STATUSES.includes(status);
}
