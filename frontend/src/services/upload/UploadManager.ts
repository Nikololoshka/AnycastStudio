import type { Dispatch, UnknownAction } from '@reduxjs/toolkit';
import type { Platform } from '../../domain/platform/types';
import type {
  PlatformPublication,
  Publication,
  PublicationError,
  PublicationStatus,
} from '../../domain/publication/types';
import type { ScheduledJob } from '../../domain/publication/planSchedule';
import type { AdapterPublication, PlatformAdapter } from '../../platforms/PlatformAdapter';
import {
  setPlatformCompleted,
  setPlatformError,
  setPlatformProgress,
  setPlatformStaged,
  setPlatformStatus,
} from '../../features/publications/publicationsSlice';
import { createLogger } from '../logs';
import { toPublicationError } from './errors';

const logger = createLogger('upload');

export interface UploadManagerDeps {
  dispatch: Dispatch<UnknownAction>;
  getAdapter: (platform: Platform) => PlatformAdapter;
  getAccountId: (platform: Platform) => string;
  getPublication: (id: string) => Publication | undefined;
}

function platformEntryOf(
  publication: Publication,
  platform: Platform,
): PlatformPublication | undefined {
  return publication.platforms.find((entry) => entry.platform === platform);
}

function contextOf(
  publication: Publication,
  entry: PlatformPublication,
  accountId: string,
): AdapterPublication {
  return {
    ...entry,
    accountId,
    video: publication.video,
    title: publication.title,
    description: publication.description,
    hashtags: publication.hashtags,
    scheduledAt: entry.scheduledAt ?? publication.scheduledAt,
  };
}

async function uploadWith(
  adapter: PlatformAdapter,
  context: AdapterPublication,
  publicationId: string,
  platform: Platform,
  deps: UploadManagerDeps,
): Promise<string> {
  deps.dispatch(setPlatformStatus({ id: publicationId, platform, status: 'validating' }));
  const validation = adapter.validate(context);
  if (!validation.valid) {
    throw {
      type: 'validation',
      message: validation.errors.join('; '),
    } satisfies PublicationError;
  }

  deps.dispatch(setPlatformStatus({ id: publicationId, platform, status: 'uploading' }));
  const uploadResult = await adapter.upload(context, (progress) => {
    deps.dispatch(setPlatformProgress({ id: publicationId, platform, ...progress }));
  });
  if (!uploadResult.success) throw uploadResult.error ?? new Error('upload failed');

  return uploadResult.videoId ?? '';
}

async function publishWith(
  adapter: PlatformAdapter,
  context: AdapterPublication,
  publicationId: string,
  platform: Platform,
  deps: UploadManagerDeps,
): Promise<void> {
  deps.dispatch(setPlatformStatus({ id: publicationId, platform, status: 'publishing' }));
  const publishResult = await adapter.publish(context);
  if (!publishResult.success) throw publishResult.error ?? new Error('publish failed');
  deps.dispatch(setPlatformCompleted({ id: publicationId, platform }));
}

async function runPhase(
  publication: Publication,
  platform: Platform,
  deps: UploadManagerDeps,
  phase: (adapter: PlatformAdapter, context: AdapterPublication) => Promise<void>,
): Promise<boolean> {
  const entry = platformEntryOf(publication, platform);
  if (!entry) return false;

  try {
    const adapter = deps.getAdapter(platform);
    const context = contextOf(publication, entry, deps.getAccountId(platform));
    await phase(adapter, context);
    return true;
  } catch (error) {
    deps.dispatch(
      setPlatformError({ id: publication.id, platform, error: toPublicationError(error) }),
    );
    return false;
  }
}

export function runPublicationTask(
  publication: Publication,
  platform: Platform,
  deps: UploadManagerDeps,
): Promise<boolean> {
  return runPhase(publication, platform, deps, async (adapter, context) => {
    const videoId = await uploadWith(adapter, context, publication.id, platform, deps);
    await publishWith(
      adapter,
      { ...context, uploadedVideoId: videoId },
      publication.id,
      platform,
      deps,
    );
  });
}

export function runNativeSchedule(
  publication: Publication,
  platform: Platform,
  deps: UploadManagerDeps,
): Promise<boolean> {
  return runPhase(publication, platform, deps, async (adapter, context) => {
    if (!adapter.schedule) throw new Error(`${platform} cannot schedule natively`);

    const videoId = await uploadWith(adapter, context, publication.id, platform, deps);
    deps.dispatch(setPlatformStatus({ id: publication.id, platform, status: 'publishing' }));

    const scheduleResult = await adapter.schedule({ ...context, uploadedVideoId: videoId });
    if (!scheduleResult.success) throw scheduleResult.error ?? new Error('schedule failed');

    deps.dispatch(setPlatformStatus({ id: publication.id, platform, status: 'scheduled' }));
  });
}

export function stagePublication(
  publication: Publication,
  platform: Platform,
  deps: UploadManagerDeps,
): Promise<boolean> {
  return runPhase(publication, platform, deps, async (adapter, context) => {
    const videoId = await uploadWith(adapter, context, publication.id, platform, deps);
    deps.dispatch(setPlatformStaged({ id: publication.id, platform, uploadedVideoId: videoId }));
  });
}

export function publishStagedPublication(
  publication: Publication,
  platform: Platform,
  deps: UploadManagerDeps,
): Promise<boolean> {
  return runPhase(publication, platform, deps, async (adapter, context) => {
    if (!context.uploadedVideoId) throw new Error(`${platform} has no staged media to publish`);
    await publishWith(adapter, context, publication.id, platform, deps);
  });
}

const IN_PROGRESS_STATUSES: PublicationStatus[] = [
  'validating',
  'preparing',
  'uploading',
  'processing',
  'publishing',
];

export type ScheduledJobOutcome = 'done' | 'failed' | 'retry';

function outcomeOf(succeeded: boolean): ScheduledJobOutcome {
  return succeeded ? 'done' : 'failed';
}

export async function runScheduledJob(
  job: ScheduledJob,
  deps: UploadManagerDeps,
): Promise<ScheduledJobOutcome> {
  const publication = deps.getPublication(job.publicationId);
  if (!publication) {
    logger.warn(`scheduled job for unknown publication ${job.publicationId}`);
    return 'failed';
  }

  const entry = platformEntryOf(publication, job.platform);
  if (!entry || entry.status === 'cancelled') return 'failed';

  if (job.phase === 'publishStaged' && !entry.uploadedVideoId) {
    if (IN_PROGRESS_STATUSES.includes(entry.status)) {
      logger.info(`${job.platform} is still uploading, retrying the scheduled publish`);
      return 'retry';
    }
  }

  logger.info(`running ${job.phase} for ${job.platform} of publication ${job.publicationId}`);

  switch (job.phase) {
    case 'stage':
      return outcomeOf(await stagePublication(publication, job.platform, deps));
    case 'publishStaged':
      return outcomeOf(await publishStagedPublication(publication, job.platform, deps));
    case 'uploadAndPublish':
      return outcomeOf(await runPublicationTask(publication, job.platform, deps));
  }
}
