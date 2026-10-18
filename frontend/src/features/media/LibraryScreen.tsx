import { useState, type Key } from 'react';
import { Button, Chip, Dropdown, Label, ListBox, Select, Spinner, Tabs } from '@heroui/react';
import { Film, MoreHorizontal, Send, Trash2, Upload } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { Link, useNavigate } from 'react-router';
import {
  useDeleteMediaAssetMutation,
  useGetDraftsQuery,
  useGetMediaAssetsQuery,
  useGetPublicationsQuery,
  videoFileOf,
  type MediaAsset,
} from '../../api';
import { messageOf, statusOf } from '../../api/errors';
import type { AppDispatch } from '../../app/store';
import { useScrolled } from '../../components/AppShell/useScrolled';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { getLabelFor } from '../../platforms/registry';
import { composerReset, setVideo } from '../composer';
import { uploadReset } from '../upload';
import { formatBytes } from './formatBytes';
import {
  bytesByCategory,
  categorizeVideos,
  sortVideos,
  type VideoCategory,
  type VideoSort,
} from './videoCategory';

type Filter = VideoCategory | 'all';

const FILTERS: Filter[] = ['all', 'published', 'draft', 'unused'];
const CATEGORIES: VideoCategory[] = ['published', 'draft', 'unused'];
const SORTS: VideoSort[] = ['newest', 'largest', 'name'];

const FILL: Record<VideoCategory, string> = {
  published: 'fill-success',
  draft: 'fill-warning',
  unused: 'fill-muted',
};

const DOT: Record<VideoCategory, string> = {
  published: 'bg-success',
  draft: 'bg-warning',
  unused: 'bg-muted',
};

const CHIP: Record<VideoCategory, 'success' | 'warning' | 'default'> = {
  published: 'success',
  draft: 'warning',
  unused: 'default',
};

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.floor(seconds % 60);
  return `${minutes.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
}

export function LibraryScreen() {
  const { t, i18n } = useTranslation('media');
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const stuck = useScrolled(240);

  const { data: library, isLoading: isLoadingAssets } = useGetMediaAssetsQuery();
  const { data: publications, isLoading: isLoadingPublications } = useGetPublicationsQuery();
  const { data: drafts, isLoading: isLoadingDrafts } = useGetDraftsQuery();
  const [deleteAsset, { isLoading: isDeleting }] = useDeleteMediaAssetMutation();

  const [filter, setFilter] = useState<Filter>('all');
  const [sort, setSort] = useState<VideoSort>('newest');
  const [pending, setPending] = useState<MediaAsset>();
  const [error, setError] = useState('');

  async function confirmDelete() {
    if (!pending) return;
    setError('');
    try {
      await deleteAsset(pending.id).unwrap();
    } catch (cause) {
      setError(
        statusOf(cause) === 'conflict'
          ? t('library.error.inUse', { name: pending.filename })
          : (messageOf(cause) ?? t('library.error.unknown')),
      );
    }
    setPending(undefined);
  }

  function compose(asset: MediaAsset) {
    dispatch(composerReset());
    dispatch(uploadReset());
    dispatch(setVideo(videoFileOf(asset)));
    void navigate('/compose');
  }

  if (isLoadingAssets || isLoadingPublications || isLoadingDrafts || !library) {
    return (
      <div className="grid place-items-center py-16">
        <Spinner />
      </div>
    );
  }

  const videos = categorizeVideos(library.assets, publications ?? [], drafts ?? []);
  const bytes = bytesByCategory(videos);
  const scale = Math.max(library.quotaBytes, library.usedBytes, 1);
  const counts: Record<Filter, number> = {
    all: videos.length,
    published: videos.filter((video) => video.category === 'published').length,
    draft: videos.filter((video) => video.category === 'draft').length,
    unused: videos.filter((video) => video.category === 'unused').length,
  };
  const visible = sortVideos(
    filter === 'all' ? videos : videos.filter((video) => video.category === filter),
    sort,
  );
  const size = (value: number) => formatBytes(value, i18n.language);

  const percentOf = (category: VideoCategory) => (bytes[category] / scale) * 100;
  const segments = CATEGORIES.map((category, index) => ({
    category,
    x: CATEGORIES.slice(0, index).reduce((sum, before) => sum + percentOf(before), 0),
    width: percentOf(category),
  }));

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('library.title')}</h1>
          <p className="mt-1 text-[15px] text-muted">{t('library.subtitle')}</p>
        </div>
        <Button variant="primary" size="lg" onPress={() => void navigate('/compose')}>
          <Upload className="size-4" />
          {t('library.upload')}
        </Button>
      </header>

      <section
        aria-labelledby="storage-heading"
        className="flex flex-col gap-3.5 rounded-[14px] bg-surface p-5 shadow-surface"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="storage-heading" className="text-lg font-semibold">
            {t('storage.title')}
          </h2>
          <span className="tabular-nums">
            <span className="text-[22px] font-semibold">{size(library.usedBytes)}</span>
            <span className="text-sm text-muted">
              {' '}
              {t('storage.ofQuota', {
                quota: size(library.quotaBytes),
                free: size(Math.max(library.quotaBytes - library.usedBytes, 0)),
              })}
            </span>
          </span>
        </div>
        <svg
          role="img"
          aria-label={CATEGORIES.map(
            (category) => `${t(`category.${category}`)} ${size(bytes[category])}`,
          ).join(', ')}
          className="h-3 w-full overflow-hidden rounded-full bg-surface-secondary"
        >
          {segments.map((segment) => (
            <rect
              key={segment.category}
              x={`${segment.x}%`}
              width={`${segment.width}%`}
              height="100%"
              className={FILL[segment.category]}
            />
          ))}
        </svg>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px]">
          {CATEGORIES.map((category) => (
            <span key={category} className="flex items-center gap-2">
              <span className={`size-2.5 rounded-full ${DOT[category]}`} />
              {t(`category.${category}`)}
              <span className="text-muted tabular-nums">{size(bytes[category])}</span>
            </span>
          ))}
          <Link
            to="/account#storage"
            className="ml-auto font-medium text-accent hover:text-accent-hover"
          >
            {t('storage.autoCleanup')}
          </Link>
        </div>
      </section>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      <Tabs
        selectedKey={filter}
        onSelectionChange={(key: Key) => setFilter(key as Filter)}
        className="gap-1"
      >
        <div
          className={[
            'sticky top-16 z-20 flex min-h-17 flex-wrap items-center gap-3 py-2',
            'before:absolute before:inset-y-0 before:-inset-x-[100vmax] before:-z-10 before:backdrop-blur-xl before:backdrop-saturate-150 before:transition-[background-color,box-shadow] motion-reduce:before:transition-none',
            stuck ? 'before:bg-surface/70 before:shadow-[0_1px_0_var(--border)]' : '',
          ].join(' ')}
        >
          <Tabs.ListContainer className="max-w-full">
            <Tabs.List aria-label={t('filter.label')}>
              {FILTERS.map((key) => (
                <Tabs.Tab key={key} id={key} className="gap-1.5 whitespace-nowrap">
                  {t(`filter.${key}`)}
                  <span className="rounded-full bg-surface-tertiary px-1.5 text-xs text-muted-strong tabular-nums">
                    {counts[key]}
                  </span>
                  <Tabs.Indicator />
                </Tabs.Tab>
              ))}
            </Tabs.List>
          </Tabs.ListContainer>
          <Select
            selectedKey={sort}
            onSelectionChange={(key) => setSort(key as VideoSort)}
            className="ml-auto w-48"
          >
            <Label className="sr-only">{t('sort.label')}</Label>
            <Select.Trigger>
              <Select.Value />
              <Select.Indicator />
            </Select.Trigger>
            <Select.Popover>
              <ListBox>
                {SORTS.map((key) => (
                  <ListBox.Item key={key} id={key} textValue={t(`sort.${key}`)}>
                    {t(`sort.${key}`)}
                  </ListBox.Item>
                ))}
              </ListBox>
            </Select.Popover>
          </Select>
        </div>

        <Tabs.Panel id={filter} className="p-0 pt-2">
          {visible.length ? (
            <ul
              aria-label={t(`filter.${filter}`)}
              className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-4"
            >
              {visible.map(({ asset, category, platforms }) => (
                <li
                  key={asset.id}
                  className="flex flex-col overflow-hidden rounded-[14px] bg-surface shadow-surface"
                >
                  <div className="relative grid aspect-video place-items-center bg-surface-secondary text-muted">
                    <Film className="size-7" />
                    <Chip
                      size="sm"
                      variant="soft"
                      color={CHIP[category]}
                      className="absolute top-2 left-2"
                    >
                      {t(`category.${category}`)}
                    </Chip>
                    {asset.durationSeconds !== null && (
                      <span className="absolute right-2 bottom-2 rounded-md bg-foreground/70 px-1.5 py-0.5 text-xs text-background tabular-nums">
                        {formatDuration(asset.durationSeconds)}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-1 flex-col gap-1.5 px-3.5 pt-3 pb-2.5">
                    <p className="truncate text-sm font-semibold" title={asset.filename}>
                      {asset.filename}
                    </p>
                    <p className="text-xs text-muted tabular-nums">
                      {size(asset.sizeBytes)} ·{' '}
                      {new Date(asset.createdAt).toLocaleDateString(i18n.language, {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}
                    </p>
                    <div className="mt-auto flex items-center justify-between gap-2">
                      <span className="flex gap-1">
                        {platforms.map((platform) => (
                          <span
                            key={platform}
                            role="img"
                            aria-label={getLabelFor(platform)}
                            title={getLabelFor(platform)}
                          >
                            <PlatformGlyph platform={platform} size="sm" />
                          </span>
                        ))}
                      </span>
                      <Dropdown>
                        <Button
                          isIconOnly
                          size="sm"
                          variant="ghost"
                          aria-label={t('library.actions', { name: asset.filename })}
                        >
                          <MoreHorizontal className="size-4" />
                        </Button>
                        <Dropdown.Popover placement="bottom end">
                          <Dropdown.Menu
                            onAction={(key) =>
                              key === 'delete' ? setPending(asset) : compose(asset)
                            }
                          >
                            <Dropdown.Item id="compose" textValue={t('library.compose')}>
                              <Send className="size-4" />
                              {t('library.compose')}
                            </Dropdown.Item>
                            <Dropdown.Item
                              id="delete"
                              variant="danger"
                              textValue={t('library.delete')}
                            >
                              <Trash2 className="size-4" />
                              {t('library.delete')}
                            </Dropdown.Item>
                          </Dropdown.Menu>
                        </Dropdown.Popover>
                      </Dropdown>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex flex-col items-center gap-3 rounded-[14px] bg-surface py-12 text-center shadow-surface">
              <Film className="size-8 text-muted" />
              <p className="text-sm text-muted">{t(`empty.${filter}`)}</p>
            </div>
          )}
        </Tabs.Panel>
      </Tabs>

      <ConfirmDialog
        isOpen={Boolean(pending)}
        heading={t('library.confirm.heading')}
        body={t('library.confirm.body', { name: pending?.filename ?? '' })}
        confirmLabel={t('library.delete')}
        isPending={isDeleting}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPending(undefined)}
      />
    </div>
  );
}
