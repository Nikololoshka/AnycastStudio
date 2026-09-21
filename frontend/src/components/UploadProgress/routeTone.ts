import type { PublicationStatus } from '../../domain/publication/types';
import { ACTIVE_STATUSES } from '../../domain/publication/status';

export type RouteTone = 'off' | 'idle' | 'active' | 'success' | 'danger';

export function routeToneOf(status: PublicationStatus, isEnabled: boolean): RouteTone {
  if (!isEnabled) return 'off';
  if (ACTIVE_STATUSES.includes(status)) return 'active';
  if (status === 'completed' || status === 'scheduled') return 'success';
  if (status === 'failed' || status === 'cancelled') return 'danger';
  return 'idle';
}

export const ROUTE_LINE_CLASSES: Record<RouteTone, string> = {
  off: 'border-route-line',
  idle: 'border-accent',
  active: 'border-accent',
  success: 'border-success',
  danger: 'border-route-line',
};
