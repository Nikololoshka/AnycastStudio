import type { Middleware, UnknownAction } from '@reduxjs/toolkit';
import { createLogger, describeValue } from '../../services/logs';

const logger = createLogger('store');

const PROGRESS_ACTION = 'publications/setPlatformProgress';
const PROGRESS_LOG_STEP = 10;

const loggedProgress = new Map<string, number>();

interface ProgressPayload {
  id: string;
  platform: string;
  percent: number;
}

function isProgressAction(
  action: UnknownAction,
): action is UnknownAction & { payload: ProgressPayload } {
  return action.type === PROGRESS_ACTION;
}

function shouldLogProgress({ id, platform, percent }: ProgressPayload): boolean {
  const key = `${id}:${platform}`;
  const last = loggedProgress.get(key);
  const step = Math.floor(percent / PROGRESS_LOG_STEP);
  if (last === step) return false;
  loggedProgress.set(key, step);
  if (percent >= 100) loggedProgress.delete(key);
  return true;
}

function errorOf(action: UnknownAction): string {
  const { error } = action as { error?: { message?: string; stack?: string } };
  if (!error) return describeValue((action as { payload?: unknown }).payload);
  return error.stack ?? error.message ?? describeValue(error);
}

export const loggingMiddleware: Middleware = () => (next) => (action) => {
  const typed = action as UnknownAction;

  if (typed.type.endsWith('/rejected')) {
    logger.error(`${typed.type} ${errorOf(typed)}`);
  } else if (typed.type === 'publications/setPlatformError') {
    logger.error(`${typed.type} ${describeValue((typed as { payload?: unknown }).payload)}`);
  } else if (typed.type.endsWith('/pending') || typed.type.endsWith('/fulfilled')) {
    logger.info(`${typed.type} ${describeValue((typed as { payload?: unknown }).payload)}`);
  } else if (isProgressAction(typed)) {
    if (shouldLogProgress(typed.payload)) {
      logger.debug(
        `${typed.type} ${typed.payload.platform} ${typed.payload.id} at ${typed.payload.percent}%`,
      );
    }
  } else {
    logger.debug(`${typed.type} ${describeValue((typed as { payload?: unknown }).payload)}`);
  }

  try {
    return next(action);
  } catch (error) {
    logger.error(`${typed.type} reducer threw ${describeValue(error)}`);
    throw error;
  }
};
