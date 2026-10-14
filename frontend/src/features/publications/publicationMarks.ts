import type { TFunction } from 'i18next';
import type { Publication, PublicationTarget } from '../../api/publicationsApi';
import { isAvailable, type AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import { publicationTab, type PublicationTab } from './publicationTab';

export type Tone = 'success' | 'warning' | 'accent' | 'danger' | 'default';

export interface TargetMark {
  platform: AvailablePlatform;
  tone: Tone;
  status: string;
}

export interface StatusChip {
  label: string;
  tone: Tone;
}

export const DOT: Record<Tone, string> = {
  success: 'bg-success',
  warning: 'bg-warning',
  accent: 'bg-accent',
  danger: 'bg-danger',
  default: 'bg-muted',
};

export function toneOf(target: PublicationTarget): Tone {
  if (target.isActive) return 'warning';
  if (target.status === 'completed') return 'success';
  if (target.status === 'scheduled') return 'accent';
  if (target.status === 'failed') return 'danger';
  return 'default';
}

export function availableTargets(publication: Publication): PublicationTarget[] {
  return publication.targets.filter((target) => isAvailable(target.platform));
}

export function targetMarks(publication: Publication, t: TFunction<'publications'>): TargetMark[] {
  return availableTargets(publication).map((target) => ({
    platform: target.platform as AvailablePlatform,
    tone: toneOf(target),
    status: t(`status.${target.status}`),
  }));
}

export function publicationChip(
  publication: Publication,
  t: TFunction<'publications'>,
): StatusChip {
  const targets = availableTargets(publication);
  const done = targets.filter((target) => target.status === 'completed').length;
  const failed = targets.filter((target) => target.status === 'failed');
  const byTab: Record<PublicationTab, StatusChip> = {
    published: publication.isActive
      ? { label: t('row.progress', { done, total: targets.length }), tone: 'warning' }
      : { label: t('status.completed'), tone: 'success' },
    scheduled: { label: t('status.scheduled'), tone: 'accent' },
    error: failed.length
      ? {
          label: t('row.failedOn', {
            platforms: failed
              .map((target) => getLabelFor(target.platform as AvailablePlatform))
              .join(', '),
          }),
          tone: 'danger',
        }
      : { label: t('status.cancelled'), tone: 'default' },
  };
  return byTab[publicationTab(publication)];
}
