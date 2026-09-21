import {
  createAsyncThunk,
  createSlice,
  type Dispatch,
  type PayloadAction,
  type UnknownAction,
} from '@reduxjs/toolkit';
import type { Platform } from '../../domain/platform/types';
import type {
  Publication,
  PublicationError,
  PublicationStatus,
} from '../../domain/publication/types';
import type { PlatformPlan, ScheduledJob } from '../../domain/publication/planSchedule';
import type { RootState } from '../../app/store';
import { buildPublicationFromComposer } from '../../domain/publication/buildPublication';
import { planPublicationSchedule } from '../../domain/publication/planSchedule';
import {
  getAdapterFor,
  getCapabilitiesFor,
  getSchedulingProfileFor,
} from '../../platforms/capabilities';
import {
  runNativeSchedule,
  runPublicationTask,
  runScheduledJob,
  stagePublication,
  type ScheduledJobOutcome,
  type UploadManagerDeps,
} from '../../services/upload';
import { scheduler } from '../../services/scheduler';
import { selectAccountByPlatform } from '../accounts/accountsSlice';

export type PublicationTask = Publication;

export interface PublicationsState {
  items: Record<string, PublicationTask>;
}

const initialState: PublicationsState = {
  items: {},
};

function createUploadDeps(
  dispatch: Dispatch<UnknownAction>,
  getState: () => RootState,
): UploadManagerDeps {
  return {
    dispatch,
    getAdapter: getAdapterFor,
    getAccountId: (platform) => {
      const account = selectAccountByPlatform(getState(), platform);
      if (!account) throw new Error(`no connected account for ${platform}`);
      return account.id;
    },
    getPublication: (id) => getState().publications.items[id],
  };
}

function runImmediatePlan(
  plan: PlatformPlan,
  publication: Publication,
  deps: UploadManagerDeps,
): Promise<boolean> {
  switch (plan.immediate) {
    case 'publish':
      return runPublicationTask(publication, plan.platform, deps);
    case 'native':
      return runNativeSchedule(publication, plan.platform, deps);
    case 'stage':
      return stagePublication(publication, plan.platform, deps);
    default:
      return Promise.resolve(true);
  }
}

export const startPublication = createAsyncThunk<string, string, { state: RootState }>(
  'publications/start',
  async (id, { dispatch, getState }) => {
    const publication = buildPublicationFromComposer(getState().composer, id);
    dispatch(createPublication(publication));

    const deps = createUploadDeps(dispatch, getState);
    const plans = planPublicationSchedule(publication, getSchedulingProfileFor, Date.now());

    for (const plan of plans) {
      if (plan.unsupported) {
        dispatch(
          setPlatformError({
            id,
            platform: plan.platform,
            error: {
              type: 'validation',
              message: `${getCapabilitiesFor(plan.platform).label} does not support scheduled publishing`,
            },
          }),
        );
        continue;
      }
      if (plan.scheduledAt) {
        dispatch(
          setPlatformScheduled({ id, platform: plan.platform, scheduledAt: plan.scheduledAt }),
        );
      }
    }

    scheduler.enqueue(plans.flatMap((plan) => plan.jobs));

    const outcomes = await Promise.all(
      plans.map(async (plan) => ({
        plan,
        succeeded: await runImmediatePlan(plan, publication, deps),
      })),
    );

    for (const { plan, succeeded } of outcomes) {
      if (!succeeded) scheduler.cancel(id, plan.platform);
    }

    return publication.id;
  },
);

export const executeScheduledJob = createAsyncThunk<
  ScheduledJobOutcome,
  ScheduledJob,
  { state: RootState }
>('publications/executeScheduledJob', (job, { dispatch, getState }) =>
  runScheduledJob(job, createUploadDeps(dispatch, getState)),
);

export const resetPublication = createAsyncThunk<void, string, { state: RootState }>(
  'publications/reset',
  (id, { dispatch }) => {
    scheduler.cancel(id);
    dispatch(clearPublication(id));
  },
);

export const cancelScheduledPublication = createAsyncThunk<
  void,
  { id: string; platform: Platform },
  { state: RootState }
>('publications/cancelSchedule', ({ id, platform }, { dispatch }) => {
  scheduler.cancel(id, platform);
  dispatch(setPlatformCancelled({ id, platform }));
});

const publicationsSlice = createSlice({
  name: 'publications',
  initialState,
  reducers: {
    createPublication(state, action: PayloadAction<Publication>) {
      state.items[action.payload.id] = action.payload;
    },
    clearPublication(state, action: PayloadAction<string>) {
      delete state.items[action.payload];
    },
    setPlatformStatus(
      state,
      action: PayloadAction<{ id: string; platform: Platform; status: PublicationStatus }>,
    ) {
      const platformPublication = state.items[action.payload.id]?.platforms.find(
        (entry) => entry.platform === action.payload.platform,
      );
      if (platformPublication) {
        platformPublication.status = action.payload.status;
        platformPublication.error = undefined;
      }
    },
    setPlatformProgress(
      state,
      action: PayloadAction<{
        id: string;
        platform: Platform;
        uploadedBytes: number;
        totalBytes: number;
        percent: number;
      }>,
    ) {
      const platformPublication = state.items[action.payload.id]?.platforms.find(
        (entry) => entry.platform === action.payload.platform,
      );
      if (platformPublication) {
        platformPublication.status = 'uploading';
        platformPublication.progress = action.payload.percent;
      }
    },
    setPlatformError(
      state,
      action: PayloadAction<{ id: string; platform: Platform; error: PublicationError }>,
    ) {
      const platformPublication = state.items[action.payload.id]?.platforms.find(
        (entry) => entry.platform === action.payload.platform,
      );
      if (platformPublication) {
        platformPublication.status = 'failed';
        platformPublication.error = action.payload.error;
      }
    },
    setPlatformCompleted(state, action: PayloadAction<{ id: string; platform: Platform }>) {
      const platformPublication = state.items[action.payload.id]?.platforms.find(
        (entry) => entry.platform === action.payload.platform,
      );
      if (platformPublication) {
        platformPublication.status = 'completed';
        platformPublication.progress = 100;
      }
    },
    setPlatformScheduled(
      state,
      action: PayloadAction<{ id: string; platform: Platform; scheduledAt: string }>,
    ) {
      const platformPublication = state.items[action.payload.id]?.platforms.find(
        (entry) => entry.platform === action.payload.platform,
      );
      if (platformPublication) {
        platformPublication.status = 'scheduled';
        platformPublication.scheduledAt = action.payload.scheduledAt;
        platformPublication.error = undefined;
      }
    },
    setPlatformStaged(
      state,
      action: PayloadAction<{ id: string; platform: Platform; uploadedVideoId: string }>,
    ) {
      const platformPublication = state.items[action.payload.id]?.platforms.find(
        (entry) => entry.platform === action.payload.platform,
      );
      if (platformPublication) {
        platformPublication.status = 'scheduled';
        platformPublication.progress = 100;
        platformPublication.uploadedVideoId = action.payload.uploadedVideoId;
        platformPublication.error = undefined;
      }
    },
    setPlatformCancelled(state, action: PayloadAction<{ id: string; platform: Platform }>) {
      const platformPublication = state.items[action.payload.id]?.platforms.find(
        (entry) => entry.platform === action.payload.platform,
      );
      if (platformPublication && platformPublication.status !== 'failed') {
        platformPublication.status = 'cancelled';
      }
    },
  },
});

export const {
  createPublication,
  clearPublication,
  setPlatformStatus,
  setPlatformProgress,
  setPlatformError,
  setPlatformCompleted,
  setPlatformScheduled,
  setPlatformStaged,
  setPlatformCancelled,
} = publicationsSlice.actions;

export default publicationsSlice.reducer;
