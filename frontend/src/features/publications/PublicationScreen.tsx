import { Chip, Spinner } from '@heroui/react';
import type { TFunction } from 'i18next';
import type { ReactNode } from 'react';
import { CalendarClock, ChevronLeft, Film, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useParams } from 'react-router';
import { useGetAccountsQuery } from '../../api/accountsApi';
import { useGetMediaAssetsQuery, videoFileOf } from '../../api/mediaApi';
import { useGetPlatformDefaultsQuery } from '../../api/platformDefaultsApi';
import {
  ACTIVE_POLL_MS,
  useGetPublicationQuery,
  type Publication,
} from '../../api/publicationsApi';
import type { AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import { formatBytes } from '../media';
import { availableTargets, DOT, publicationChip, toneOf, type Tone } from './publicationMarks';
import { TargetCard } from './TargetCard';

const CARD = 'rounded-[14px] bg-surface shadow-surface';

interface HistoryEvent {
  key: string;
  text: string;
  at: string;
  tone: Tone;
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.floor(seconds % 60);
  return `${minutes.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
}

export function PublicationScreen() {
  const { t, i18n } = useTranslation('publications');
  const { id } = useParams();
  const publicationId = Number(id);

  const {
    data: publication,
    isLoading,
    isError,
  } = useGetPublicationQuery(publicationId, {
    skip: !Number.isFinite(publicationId),
    pollingInterval: ACTIVE_POLL_MS,
    skipPollingIfUnfocused: true,
  });
  const { data: accounts } = useGetAccountsQuery();
  const { data: defaults } = useGetPlatformDefaultsQuery();

  if (!Number.isFinite(publicationId) || isError) return <Navigate to="/publications" replace />;

  if (isLoading || !publication) {
    return (
      <div className="grid place-items-center py-16">
        <Spinner />
      </div>
    );
  }

  const chip = publicationChip(publication, t);
  const formatDate = (iso: string) =>
    new Date(iso).toLocaleString(i18n.language, { dateStyle: 'medium', timeStyle: 'short' });

  return (
    <div className="mx-auto flex w-full max-w-300 flex-col gap-5">
      <Link
        to="/publications"
        className="inline-flex min-h-8 items-center gap-1.5 self-start text-sm font-medium text-accent hover:text-accent-hover"
      >
        <ChevronLeft className="size-4" />
        {t('detail.back')}
      </Link>

      <header className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1
            className={`text-3xl font-bold tracking-tight ${publication.title ? '' : 'text-muted'}`}
          >
            {publication.title || t('screen.untitled')}
          </h1>
          <Chip size="sm" variant="soft" color={chip.tone}>
            {chip.label}
          </Chip>
        </div>
        <p className="flex flex-wrap gap-x-3.5 gap-y-1 text-sm text-muted">
          {publication.publishAt ? (
            <span className="inline-flex items-center gap-1.5 tabular-nums">
              <CalendarClock className="size-4" />
              {formatDate(publication.publishAt)}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5">
              <Zap className="size-4" />
              {t('detail.immediate')}
            </span>
          )}
          <span className="tabular-nums">
            {t('detail.created', { time: formatDate(publication.createdAt) })}
          </span>
        </p>
      </header>

      <div className="grid items-start gap-6 min-[1100px]:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <section aria-label={t('column.platforms')} className="flex min-w-0 flex-col gap-4">
          {availableTargets(publication).map((target) => (
            <TargetCard
              key={target.id}
              publication={publication}
              target={target}
              accountName={
                accounts?.find((account) => account.id === target.socialAccountId)?.displayName
              }
              defaults={defaults}
            />
          ))}
          <p className="flex flex-wrap items-center gap-2 px-1 text-xs text-muted">
            <Chip size="sm" variant="soft" color="accent">
              {t('detail.changed')}
            </Chip>
            {t('detail.legend')}
          </p>
        </section>

        <aside className="flex min-w-0 flex-col gap-4 min-[1100px]:sticky min-[1100px]:top-22">
          <VideoCard publication={publication} />

          <section aria-labelledby="common-heading" className={`${CARD} flex flex-col gap-3.5 p-4`}>
            <h2 id="common-heading" className="text-[17px] font-semibold">
              {t('detail.common')}
            </h2>
            <Field label={t('detail.text.title')}>
              <p className="text-sm font-medium">{publication.title || '—'}</p>
            </Field>
            <Field label={t('detail.text.description')}>
              <p className="text-sm whitespace-pre-wrap">{publication.description || '—'}</p>
            </Field>
            {publication.hashtags.length > 0 && (
              <Field label={t('detail.hashtags')}>
                <div className="flex flex-wrap gap-1.5">
                  {publication.hashtags.map((tag) => (
                    <Chip key={tag} size="sm" variant="soft">
                      #{tag}
                    </Chip>
                  ))}
                </div>
              </Field>
            )}
          </section>

          <section aria-labelledby="history-heading" className={`${CARD} flex flex-col gap-3 p-4`}>
            <h2 id="history-heading" className="text-[17px] font-semibold">
              {t('detail.history')}
            </h2>
            <ol className="flex flex-col">
              {historyOf(publication, t).map((event, index, events) => (
                <li key={event.key} className="flex gap-3">
                  <span className="flex w-3 shrink-0 flex-col items-center">
                    <span className={`mt-1 size-2.5 shrink-0 rounded-full ${DOT[event.tone]}`} />
                    {index < events.length - 1 && (
                      <span className="my-1 min-h-3.5 w-0.5 flex-1 bg-separator" />
                    )}
                  </span>
                  <span className="min-w-0 pb-3">
                    <span className="block text-[13px]">{event.text}</span>
                    <span className="block text-xs text-muted tabular-nums">
                      {formatDate(event.at)}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </div>
  );
}

function historyOf(publication: Publication, t: TFunction<'publications'>): HistoryEvent[] {
  const events: HistoryEvent[] = [
    { key: 'created', text: t('detail.event.created'), at: publication.createdAt, tone: 'default' },
  ];
  for (const target of availableTargets(publication)) {
    const platform = getLabelFor(target.platform as AvailablePlatform);
    if (target.startedAt) {
      events.push({
        key: `${target.id}-started`,
        text: t('detail.event.started', { platform }),
        at: target.startedAt,
        tone: 'default',
      });
    }
    if (target.finishedAt) {
      events.push({
        key: `${target.id}-finished`,
        text: t('detail.event.finished', { platform, status: t(`status.${target.status}`) }),
        at: target.finishedAt,
        tone: toneOf(target),
      });
    }
  }
  return events.sort((a, b) => a.at.localeCompare(b.at));
}

function VideoCard({ publication }: { publication: Publication }) {
  const { t, i18n } = useTranslation('publications');
  const { data: library } = useGetMediaAssetsQuery();
  const asset = library?.assets.find((item) => item.id === publication.mediaAssetId);
  const video = asset && videoFileOf(asset);

  return (
    <section aria-label={t('detail.video')} className={`${CARD} overflow-hidden`}>
      <div className="relative grid h-45 place-items-center bg-surface-tertiary text-muted">
        {video?.thumbnailUrl ? (
          <img src={video.thumbnailUrl} alt="" className="size-full object-contain" />
        ) : (
          <Film className="size-6" />
        )}
        {video?.duration && (
          <span className="absolute right-2 bottom-2 rounded-md bg-black/60 px-1.5 py-0.5 text-xs text-white tabular-nums">
            {formatDuration(video.duration)}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1 px-4 py-3.5">
        <p className="truncate text-sm font-medium">{publication.filename}</p>
        {video && (
          <p className="text-xs text-muted tabular-nums">
            {[
              formatBytes(video.size, i18n.language),
              video.width && video.height && `${video.width}×${video.height}`,
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
        )}
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-xs text-muted">{label}</p>
      {children}
    </div>
  );
}
