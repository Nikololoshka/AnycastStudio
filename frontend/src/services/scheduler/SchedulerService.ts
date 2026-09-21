import type { Platform } from '../../domain/platform/types';
import type { ScheduledJob } from '../../domain/publication/planSchedule';
import { createLogger } from '../logs';

const TICK_INTERVAL_MS = 5_000;
const RETRY_DELAY_MS = 5_000;

export type ScheduledJobRunner = (job: ScheduledJob) => Promise<'done' | 'failed' | 'retry'>;

function keyOf(job: ScheduledJob): string {
  return `${job.publicationId}:${job.platform}:${job.phase}`;
}

export class SchedulerService {
  private readonly jobs = new Map<string, ScheduledJob>();
  private readonly running = new Set<string>();
  private readonly logger = createLogger('scheduler');
  private timer?: ReturnType<typeof setInterval>;
  private runner?: ScheduledJobRunner;

  start(runner: ScheduledJobRunner): void {
    this.runner = runner;
    if (this.timer) return;
    this.timer = setInterval(() => void this.tick(), TICK_INTERVAL_MS);
    this.logger.info('scheduler started');
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
    this.runner = undefined;
    this.logger.info('scheduler stopped');
  }

  enqueue(jobs: ScheduledJob[]): void {
    for (const job of jobs) {
      this.jobs.set(keyOf(job), job);
      this.logger.info(
        `queued ${job.phase} for ${job.platform} at ${new Date(job.runAt).toISOString()}`,
      );
    }
  }

  cancel(publicationId: string, platform?: Platform): void {
    for (const [key, job] of this.jobs) {
      if (job.publicationId !== publicationId) continue;
      if (platform && job.platform !== platform) continue;
      this.jobs.delete(key);
      this.logger.info(`cancelled ${job.phase} for ${job.platform}`);
    }
  }

  listJobs(): ScheduledJob[] {
    return [...this.jobs.values()];
  }

  private async tick(): Promise<void> {
    const runner = this.runner;
    if (!runner) return;

    const due = [...this.jobs.values()].filter(
      (job) => job.runAt <= Date.now() && !this.running.has(keyOf(job)),
    );

    await Promise.allSettled(
      due.map(async (job) => {
        const key = keyOf(job);
        this.running.add(key);
        this.jobs.delete(key);
        try {
          const outcome = await runner(job);
          if (outcome === 'retry') {
            this.jobs.set(key, { ...job, runAt: Date.now() + RETRY_DELAY_MS });
          }
        } catch (error) {
          this.logger.error(`job ${key} threw: ${String(error)}`);
        } finally {
          this.running.delete(key);
        }
      }),
    );
  }
}

export const scheduler = new SchedulerService();
