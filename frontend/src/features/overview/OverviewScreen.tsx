import { Button, Chip, ProgressBar, Spinner, Table } from '@heroui/react';
import { Film, Plus, Radio } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { Link, useNavigate } from 'react-router';
import {
  ACTIVE_POLL_MS,
  publicationsApi,
  useGetAccountsQuery,
  useGetDraftsQuery,
  useGetMediaAssetsQuery,
  useGetPublicationsQuery,
  type Publication,
  type PublicationTarget,
} from '../../api';
import type { AppDispatch } from '../../app/store';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { INDETERMINATE_STATUSES } from '../../domain/publication/status';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import { AccountStateChip } from '../accounts';
import { composerReset } from '../composer';
import { formatBytes } from '../media';
import { availableTargets, publicationChip, TargetMarks, targetMarks } from '../publications';
import { uploadReset } from '../upload';
import { overviewStats } from './overviewStats';

const CARD = 'rounded-[14px] bg-surface shadow-surface';
const LINK = 'text-sm font-medium text-accent hover:text-accent-hover';
const FOCUS = 'outline-none focus-visible:ring-2 focus-visible:ring-focus';

function newest<T>(items: T[], dateOf: (item: T) => string): T[] {
  return [...items].sort((a, b) => dateOf(b).localeCompare(dateOf(a)));
}

function ActiveTarget({ target }: { target: PublicationTarget }) {
  const { t } = useTranslation('overview');
  const { t: tp } = useTranslation('publications');
  const platform = target.platform as AvailablePlatform;
  const isDone = target.status === 'completed';
  const isFailed = target.status === 'failed' || target.status === 'cancelled';
  const isIndeterminate = INDETERMINATE_STATUSES.includes(target.status);
  const label = isDone
    ? t('active.done')
    : target.status === 'uploading'
      ? `${Math.round(target.progress)}%`
      : tp(`status.${target.status}`);

  return (
    <li className="flex items-center gap-3 rounded-xl bg-surface-secondary p-3">
      <PlatformGlyph platform={platform} size="sm" />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex justify-between gap-2 text-sm">
          <span className="truncate">{getLabelFor(platform)}</span>
          <span
            className={`font-medium whitespace-nowrap tabular-nums ${
              isDone ? 'text-success' : isFailed ? 'text-danger' : 'text-muted'
            }`}
          >
            {label}
          </span>
        </div>
        <ProgressBar
          aria-label={`${getLabelFor(platform)}: ${label}`}
          value={isDone ? 100 : target.progress}
          isIndeterminate={target.isActive && isIndeterminate}
          color={isDone ? 'success' : isFailed ? 'danger' : 'accent'}
          size="sm"
        >
          <ProgressBar.Track>
            <ProgressBar.Fill />
          </ProgressBar.Track>
        </ProgressBar>
      </div>
    </li>
  );
}

function ActiveCard({
  publication,
  onCompose,
}: {
  publication?: Publication;
  onCompose: () => void;
}) {
  const { t } = useTranslation('overview');
  const { t: tp } = useTranslation('publications');

  if (!publication) {
    return (
      <section
        aria-labelledby="active-heading"
        className={`${CARD} flex flex-wrap items-center gap-4 p-5`}
      >
        <span className="grid size-11 shrink-0 place-items-center rounded-full bg-surface-secondary text-muted">
          <Radio className="size-5" />
        </span>
        <div className="min-w-48 flex-1">
          <h2 id="active-heading" className="text-[15px] font-semibold">
            {t('active.emptyTitle')}
          </h2>
          <p className="text-sm text-muted">{t('active.emptyBody')}</p>
        </div>
        <Button variant="tertiary" onPress={onCompose}>
          {t('active.compose')}
        </Button>
      </section>
    );
  }

  const chip = publicationChip(publication, tp);

  return (
    <section aria-labelledby="active-heading" className={`${CARD} flex flex-col gap-4 p-5`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="active-heading" className="text-lg font-semibold">
          {t('active.title')}
        </h2>
        <Chip size="sm" variant="soft" color={chip.tone}>
          {chip.label}
        </Chip>
      </div>
      <Link
        to={`/publications/${publication.id}`}
        className={`flex items-center gap-4 rounded-xl ${FOCUS}`}
      >
        <span className="grid h-16 w-28 shrink-0 place-items-center rounded-xl bg-surface-tertiary text-muted">
          <Film className="size-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-base font-semibold">
            {publication.title || t('screen.untitled')}
          </span>
          <span className="block truncate text-[13px] text-muted">{publication.filename}</span>
        </span>
      </Link>
      <ul className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
        {availableTargets(publication).map((target) => (
          <ActiveTarget key={target.id} target={target} />
        ))}
      </ul>
    </section>
  );
}

export function OverviewScreen() {
  const { t, i18n } = useTranslation('overview');
  const { t: tp } = useTranslation('publications');
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();

  const { data: cached } = publicationsApi.endpoints.getPublications.useQueryState(undefined);
  const { data: publications, isLoading: isLoadingPublications } = useGetPublicationsQuery(
    undefined,
    {
      pollingInterval: cached?.some((publication) => publication.isActive) ? ACTIVE_POLL_MS : 0,
      skipPollingIfUnfocused: true,
    },
  );
  const { data: library, isLoading: isLoadingAssets } = useGetMediaAssetsQuery();
  const { data: drafts, isLoading: isLoadingDrafts } = useGetDraftsQuery();
  const { data: accounts, isLoading: isLoadingAccounts } = useGetAccountsQuery();

  function startNew() {
    dispatch(composerReset());
    dispatch(uploadReset());
    void navigate('/compose');
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString(i18n.language, {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  if (isLoadingPublications || isLoadingAssets || isLoadingDrafts || isLoadingAccounts) {
    return (
      <div className="grid place-items-center py-16">
        <Spinner />
      </div>
    );
  }

  const sorted = newest(publications ?? [], (publication) => publication.createdAt);
  const recentDrafts = newest(drafts ?? [], (draft) => draft.updatedAt).slice(0, 3);
  const stats = overviewStats(library?.assets ?? [], sorted, drafts ?? [], new Date());
  const size = (bytes: number) => formatBytes(bytes, i18n.language);

  const cards = [
    {
      key: 'videos',
      to: '/library',
      label: t('stats.videos'),
      value: stats.videos,
      sub: t('stats.unpublished', { count: stats.unpublishedVideos }),
    },
    {
      key: 'publications',
      to: '/publications',
      label: t('stats.publications'),
      value: stats.recentPublications,
      sub: t('stats.platforms', { count: stats.recentPlatforms }),
    },
    {
      key: 'drafts',
      to: '/publications?tab=draft',
      label: t('stats.drafts'),
      value: stats.drafts,
      sub: t('stats.scheduled', { count: stats.scheduled }),
    },
    {
      key: 'storage',
      to: '/library',
      label: t('stats.storage'),
      value: size(library?.usedBytes ?? 0),
      sub: t('stats.quota', { quota: size(library?.quotaBytes ?? 0) }),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('screen.title')}</h1>
          <p className="mt-1 text-[15px] text-muted">{t('screen.subtitle')}</p>
        </div>
        <Button variant="primary" size="lg" onPress={startNew}>
          <Plus className="size-4" />
          {t('screen.new')}
        </Button>
      </header>

      <section
        aria-label={t('stats.label')}
        className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-4"
      >
        {cards.map((card) => (
          <Link
            key={card.key}
            to={card.to}
            className={`${CARD} ${FOCUS} flex flex-col gap-1.5 p-5 transition-colors hover:bg-surface-secondary`}
          >
            <span className="text-sm text-muted">{card.label}</span>
            <span className="text-3xl font-semibold tracking-tight tabular-nums">{card.value}</span>
            <span className="text-[13px] text-muted">{card.sub}</span>
          </Link>
        ))}
      </section>

      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-[2_1_560px] flex-col gap-6">
          <ActiveCard
            publication={sorted.find((publication) => publication.isActive)}
            onCompose={startNew}
          />

          <section aria-labelledby="recent-heading" className={`${CARD} p-4`}>
            <div className="flex items-center justify-between px-1 pt-1 pb-3">
              <h2 id="recent-heading" className="text-lg font-semibold">
                {t('recent.title')}
              </h2>
              <Link to="/publications" className={LINK}>
                {t('recent.all')}
              </Link>
            </div>
            <Table variant="secondary">
              <Table.ScrollContainer>
                <Table.Content aria-labelledby="recent-heading" className="min-w-[600px]">
                  <Table.Header>
                    <Table.Column isRowHeader>{t('recent.column.video')}</Table.Column>
                    <Table.Column>{t('recent.column.platforms')}</Table.Column>
                    <Table.Column>{t('recent.column.status')}</Table.Column>
                    <Table.Column>{t('recent.column.when')}</Table.Column>
                  </Table.Header>
                  <Table.Body
                    renderEmptyState={() => (
                      <p className="py-10 text-center text-sm text-muted">{t('recent.empty')}</p>
                    )}
                  >
                    {sorted.slice(0, 5).map((publication) => {
                      const chip = publicationChip(publication, tp);
                      return (
                        <Table.Row
                          key={publication.id}
                          id={publication.id}
                          onAction={() => void navigate(`/publications/${publication.id}`)}
                          className="cursor-pointer"
                        >
                          <Table.Cell>
                            <span
                              className={`font-medium ${publication.title ? '' : 'text-muted'}`}
                            >
                              {publication.title || t('screen.untitled')}
                            </span>
                          </Table.Cell>
                          <Table.Cell>
                            <TargetMarks marks={targetMarks(publication, tp)} />
                          </Table.Cell>
                          <Table.Cell>
                            <Chip size="sm" variant="soft" color={chip.tone}>
                              {chip.label}
                            </Chip>
                          </Table.Cell>
                          <Table.Cell className="text-[13px] whitespace-nowrap text-muted tabular-nums">
                            {formatDate(publication.publishAt ?? publication.createdAt)}
                          </Table.Cell>
                        </Table.Row>
                      );
                    })}
                  </Table.Body>
                </Table.Content>
              </Table.ScrollContainer>
            </Table>
          </section>
        </div>

        <div className="flex min-w-0 flex-[1_1_300px] flex-col gap-6">
          <section
            aria-labelledby="platforms-heading"
            className={`${CARD} flex flex-col gap-1 p-5`}
          >
            <div className="mb-2 flex items-center justify-between">
              <h2 id="platforms-heading" className="text-lg font-semibold">
                {t('platforms.title')}
              </h2>
              <Link to="/platforms" className={LINK}>
                {t('platforms.manage')}
              </Link>
            </div>
            <ul>
              {AVAILABLE_PLATFORMS.map((platform) => {
                const account = accounts?.find((candidate) => candidate.platform === platform);
                return (
                  <li key={platform} className="flex min-h-13 items-center gap-3">
                    <PlatformGlyph platform={platform} className={account ? '' : 'opacity-50'} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">{getLabelFor(platform)}</span>
                      <span className="block truncate text-xs text-muted">
                        {account?.displayName}
                      </span>
                    </span>
                    <AccountStateChip account={account} />
                  </li>
                );
              })}
            </ul>
          </section>

          <section aria-labelledby="drafts-heading" className={`${CARD} flex flex-col gap-2 p-5`}>
            <div className="flex items-center justify-between">
              <h2 id="drafts-heading" className="text-lg font-semibold">
                {t('drafts.title')}
              </h2>
              <Link to="/publications?tab=draft" className={LINK}>
                {t('drafts.all')}
              </Link>
            </div>
            {recentDrafts.length ? (
              <ul className="-mx-2">
                {recentDrafts.map((draft) => (
                  <li key={draft.id}>
                    <Link
                      to={`/compose/${draft.id}`}
                      className={`flex items-center gap-3 rounded-xl p-2 hover:bg-surface-secondary ${FOCUS}`}
                    >
                      <span className="grid h-9 w-14 shrink-0 place-items-center rounded-lg bg-surface-tertiary text-muted">
                        <Film className="size-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span
                          className={`block truncate text-sm font-medium ${draft.title ? '' : 'text-muted'}`}
                        >
                          {draft.title || t('screen.untitled')}
                        </span>
                        <span className="block text-xs text-muted tabular-nums">
                          {t('drafts.edited', { date: formatDate(draft.updatedAt) })}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-4 text-sm text-muted">{t('drafts.empty')}</p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
