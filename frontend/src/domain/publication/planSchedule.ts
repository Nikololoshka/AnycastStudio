import type { Platform, PlatformSettings, SchedulingMode } from '../platform/types';
import type { Publication } from './types';

export interface SchedulingProfile {
  mode: SchedulingMode;
  stagedMediaTtlMs?: number;
}

export type ScheduledPhase = 'stage' | 'publishStaged' | 'uploadAndPublish';

export type ImmediateAction = 'publish' | 'native' | 'stage';

export interface ScheduledJob {
  publicationId: string;
  platform: Platform;
  phase: ScheduledPhase;
  runAt: number;
}

export interface PlatformPlan {
  platform: Platform;
  immediate?: ImmediateAction;
  jobs: ScheduledJob[];
  scheduledAt?: string;
  unsupported?: boolean;
}

function stageLeadOf(profile: SchedulingProfile): number {
  return profile.stagedMediaTtlMs
    ? Math.floor(profile.stagedMediaTtlMs / 2)
    : Number.POSITIVE_INFINITY;
}

function planFor(
  publication: Publication,
  platform: Platform,
  profile: SchedulingProfile,
  publishAt: number,
  now: number,
): PlatformPlan {
  const scheduledAt = new Date(publishAt).toISOString();
  const job = (phase: ScheduledPhase, runAt: number): ScheduledJob => ({
    publicationId: publication.id,
    platform,
    phase,
    runAt,
  });

  switch (profile.mode) {
    case 'native':
      return { platform, immediate: 'native', jobs: [] };

    case 'stagedPublish': {
      const stageAt = publishAt - stageLeadOf(profile);
      const publishJob = job('publishStaged', publishAt);
      return stageAt <= now
        ? { platform, immediate: 'stage', jobs: [publishJob], scheduledAt }
        : { platform, jobs: [job('stage', stageAt), publishJob], scheduledAt };
    }

    case 'deferredUpload':
      return { platform, jobs: [job('uploadAndPublish', publishAt)], scheduledAt };

    case 'unsupported':
      return { platform, jobs: [], unsupported: true };
  }
}

export function planPublicationSchedule(
  publication: Publication,
  profileOf: (platform: Platform, settings: PlatformSettings) => SchedulingProfile,
  now: number,
): PlatformPlan[] {
  const entries = publication.platforms.filter((entry) => entry.enabled);

  const publishAt = publication.scheduledAt ? Date.parse(publication.scheduledAt) : Number.NaN;

  if (!Number.isFinite(publishAt) || publishAt <= now) {
    return entries.map((entry) => ({
      platform: entry.platform,
      immediate: 'publish' as const,
      jobs: [],
    }));
  }

  return entries.map((entry) =>
    planFor(publication, entry.platform, profileOf(entry.platform, entry.settings), publishAt, now),
  );
}
