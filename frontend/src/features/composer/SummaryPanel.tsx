import { useState } from 'react';
import { Button } from '@heroui/react';
import { CalendarClock, Clapperboard, RotateCcw, Send, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { UploadProgressList } from '../../components/UploadProgress';
import type { AppDispatch, RootState } from '../../app/store';
import { resetPublication, startPublication } from '../publications/publicationsSlice';
import { isActiveStatus } from '../../domain/publication/status';

const SCHEDULE_FORMAT: Intl.DateTimeFormatOptions = {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
};

export function SummaryPanel() {
  const { t, i18n } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const { video, title, scheduledAt, selectedPlatforms } = useSelector(
    (state: RootState) => state.composer,
  );
  const connectedPlatforms = useSelector(
    (state: RootState) => Object.values(state.accounts.items).length,
  );
  const [publicationId, setPublicationId] = useState<string>();
  const [isPublishing, setIsPublishing] = useState(false);
  const publicationPlatforms = useSelector((state: RootState) =>
    publicationId ? state.publications.items[publicationId]?.platforms : undefined,
  );

  const statuses = (publicationPlatforms ?? [])
    .filter((entry) => entry.enabled)
    .map((entry) => entry.status);
  const isRunning = statuses.some(isActiveStatus);
  const isScheduled = statuses.some((status) => status === 'scheduled');
  const isFinished =
    statuses.length > 0 &&
    !isPublishing &&
    !isRunning &&
    !isScheduled &&
    !statuses.includes('idle');

  async function publish() {
    const id = crypto.randomUUID();
    setPublicationId(id);
    setIsPublishing(true);
    try {
      await dispatch(startPublication(id)).unwrap();
    } finally {
      setIsPublishing(false);
    }
  }

  function startOver() {
    if (publicationId) void dispatch(resetPublication(publicationId));
    setPublicationId(undefined);
  }

  const blocker = !video
    ? t('summary.needsVideo')
    : selectedPlatforms.length === 0
      ? t('summary.needsPlatform')
      : undefined;
  const actionLabel = scheduledAt ? t('summary.schedule') : t('summary.publish');
  const pendingLabel = scheduledAt ? t('summary.scheduling') : t('summary.publishing');

  return (
    <div className="flex h-full flex-col">
      <header className="px-6 pt-7 pb-4">
        <h2 className="font-display text-xl font-semibold tracking-tight">{t('summary.title')}</h2>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-4">
        <div className="overflow-hidden rounded-2xl border border-border bg-surface-secondary">
          <div className="relative aspect-video bg-surface-tertiary">
            {video?.thumbnailPath ? (
              <img src={video.thumbnailPath} alt="" className="size-full object-cover" />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted">
                <Clapperboard className="size-6" />
                <span className="text-sm">{t('summary.noVideo')}</span>
              </div>
            )}
          </div>
          <div className="px-4 py-3">
            <p className={`truncate font-medium ${title ? '' : 'text-muted'}`}>
              {title || t('summary.untitled')}
            </p>
            <p className="truncate text-xs text-muted">{video?.name ?? t('summary.chooseVideo')}</p>
          </div>
        </div>

        {connectedPlatforms === 0 && selectedPlatforms.length === 0 ? (
          <p className="pl-9 text-sm text-muted">{t('summary.noAccounts')}</p>
        ) : (
          <UploadProgressList selectedPlatforms={selectedPlatforms} publicationId={publicationId} />
        )}
      </div>

      <footer className="flex flex-col gap-3 border-t border-separator px-6 py-5">
        <p className="flex items-center gap-2 text-sm text-muted">
          {scheduledAt ? (
            <>
              <CalendarClock className="size-4" />
              <span className="tabular-nums">
                {new Date(scheduledAt).toLocaleString(i18n.language, SCHEDULE_FORMAT)}
              </span>
            </>
          ) : (
            <>
              <Zap className="size-4" />
              {t('summary.immediate')}
            </>
          )}
        </p>

        {isFinished ? (
          <Button variant="secondary" size="lg" fullWidth onPress={startOver}>
            <RotateCcw className="size-4" />
            {t('summary.reset')}
          </Button>
        ) : (
          <Button
            variant="primary"
            size="lg"
            fullWidth
            isDisabled={Boolean(blocker) || isRunning || isScheduled}
            isPending={isPublishing}
            onPress={publish}
          >
            <Send className="size-4" />
            {isPublishing ? pendingLabel : actionLabel}
          </Button>
        )}
        {blocker && !isFinished && <p className="text-center text-xs text-muted">{blocker}</p>}
      </footer>
    </div>
  );
}
