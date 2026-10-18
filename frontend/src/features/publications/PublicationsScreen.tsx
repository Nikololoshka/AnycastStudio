import { useState, type Key } from 'react';
import {
  Button,
  Chip,
  Label,
  ListBox,
  Pagination,
  Select,
  Spinner,
  Table,
  Tabs,
} from '@heroui/react';
import { Film, Plus, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useNavigate, useSearchParams } from 'react-router';
import {
  ACTIVE_POLL_MS,
  publicationsApi,
  useDeletePublicationMutation,
  useGetPublicationsQuery,
  type Publication,
} from '../../api/publicationsApi';
import { useDeleteDraftMutation, useGetDraftsQuery, type Draft } from '../../api/draftsApi';
import type { AppDispatch } from '../../app/store';
import { useScrolled } from '../../components/AppShell/useScrolled';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { resetComposer } from '../composer';
import { uploadReset } from '../upload';
import { publicationTab, type PublicationTab } from './publicationTab';
import {
  DOT,
  publicationChip,
  targetMarks,
  type StatusChip,
  type TargetMark,
  type Tone,
} from './publicationMarks';
import { TargetMarks } from './TargetMarks';

type ScreenTab = PublicationTab | 'draft';

interface Row {
  key: string;
  kind: 'draft' | 'publication';
  id: number;
  title: string;
  marks: TargetMark[];
  chip: StatusChip;
  date: string;
  action: { label?: string; to: string };
}

const TABS: ScreenTab[] = ['published', 'scheduled', 'draft', 'error'];
const PAGE_SIZES = [10, 25, 50];
const STICKY_COLUMN = 'z-10 min-[900px]:sticky min-[900px]:top-33';

const LEGEND: { key: 'completed' | 'active' | 'scheduled' | 'failed'; tone: Tone }[] = [
  { key: 'completed', tone: 'success' },
  { key: 'active', tone: 'warning' },
  { key: 'scheduled', tone: 'accent' },
  { key: 'failed', tone: 'danger' },
];

const DETAIL_COLUMN: Record<ScreenTab, 'status' | 'reason' | 'remaining'> = {
  published: 'status',
  scheduled: 'status',
  draft: 'remaining',
  error: 'reason',
};

const DATE_COLUMN: Record<ScreenTab, 'date' | 'publishAt' | 'updated'> = {
  published: 'date',
  scheduled: 'publishAt',
  draft: 'updated',
  error: 'date',
};

export function PublicationsScreen() {
  const { t, i18n } = useTranslation('publications');
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const stuck = useScrolled(90);

  const { data: cached } = publicationsApi.endpoints.getPublications.useQueryState(undefined);
  const { data: publications, isLoading: isLoadingPublications } = useGetPublicationsQuery(
    undefined,
    {
      pollingInterval: cached?.some((publication) => publication.isActive) ? ACTIVE_POLL_MS : 0,
      skipPollingIfUnfocused: true,
    },
  );
  const { data: drafts, isLoading: isLoadingDrafts } = useGetDraftsQuery();
  const [deleteDraft, { isLoading: isDeletingDraft }] = useDeleteDraftMutation();
  const [deletePublication, { isLoading: isDeletingPublication }] = useDeletePublicationMutation();

  const [params, setParams] = useSearchParams();
  const tab = TABS.find((key) => key === params.get('tab')) ?? 'published';
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZES[0]);
  const [pending, setPending] = useState<Row>();

  const grouped: Record<ScreenTab, Publication[]> = {
    published: [],
    scheduled: [],
    draft: [],
    error: [],
  };
  for (const publication of [...(publications ?? [])].sort((a, b) =>
    b.createdAt.localeCompare(a.createdAt),
  )) {
    grouped[publicationTab(publication)].push(publication);
  }

  const counts: Record<ScreenTab, number> = {
    published: grouped.published.length,
    scheduled: grouped.scheduled.length,
    draft: drafts?.length ?? 0,
    error: grouped.error.length,
  };

  function publicationRow(publication: Publication): Row {
    const to = `/publications/${publication.id}`;
    const tab = publicationTab(publication);

    return {
      key: `publication-${publication.id}`,
      kind: 'publication',
      id: publication.id,
      title: publication.title,
      marks: targetMarks(publication, t),
      chip: publicationChip(publication, t),
      date:
        tab === 'scheduled'
          ? (publication.publishAt ?? publication.createdAt)
          : publication.createdAt,
      action: { label: tab === 'error' ? t('actions.retry') : undefined, to },
    };
  }

  function draftRow(draft: Draft): Row {
    const gap = !draft.video
      ? 'noVideo'
      : !draft.title.trim()
        ? 'noTitle'
        : draft.selectedPlatforms.length === 0
          ? 'noPlatforms'
          : undefined;
    return {
      key: `draft-${draft.id}`,
      kind: 'draft',
      id: draft.id,
      title: draft.title,
      marks: draft.selectedPlatforms.map((platform) => ({
        platform,
        tone: 'default',
        status: t('tabs.draft'),
      })),
      chip: gap
        ? { label: t(`row.${gap}`), tone: 'default' }
        : { label: t('row.ready'), tone: 'success' },
      date: draft.updatedAt,
      action: { label: t('actions.continue'), to: `/compose/${draft.id}` },
    };
  }

  const rows = tab === 'draft' ? (drafts ?? []).map(draftRow) : grouped[tab].map(publicationRow);
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const from = (currentPage - 1) * pageSize;
  const visible = rows.slice(from, from + pageSize);

  function startNew() {
    dispatch(resetComposer());
    dispatch(uploadReset());
    void navigate('/compose');
  }

  async function confirmDelete() {
    if (!pending) return;
    if (pending.kind === 'draft') {
      await deleteDraft(pending.id);
    } else {
      await deletePublication(pending.id);
    }
    setPending(undefined);
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString(i18n.language, {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  if (isLoadingPublications || isLoadingDrafts) {
    return (
      <div className="grid place-items-center py-16">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
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

      <Tabs
        selectedKey={tab}
        onSelectionChange={(key: Key) => {
          const next = new URLSearchParams(params);
          next.set('tab', String(key));
          setParams(next, { replace: true });
          setPage(1);
        }}
        className="gap-1"
      >
        <div
          className={[
            'sticky top-16 z-20 flex h-17 items-center',
            'before:absolute before:inset-y-0 before:-inset-x-[100vmax] before:-z-10 before:backdrop-blur-xl before:backdrop-saturate-150 before:transition-[background-color,box-shadow] motion-reduce:before:transition-none',
            stuck ? 'before:bg-surface/70 before:shadow-[0_1px_0_var(--border)]' : '',
          ].join(' ')}
        >
          <Tabs.ListContainer className="max-w-full">
            <Tabs.List aria-label={t('tabs.label')}>
              {TABS.map((key) => (
                <Tabs.Tab key={key} id={key} className="gap-1.5 whitespace-nowrap">
                  {t(`tabs.${key}`)}
                  <span
                    className={[
                      'rounded-full px-1.5 text-xs tabular-nums',
                      key === 'error' && counts.error > 0
                        ? 'bg-danger-soft text-danger-soft-foreground'
                        : 'bg-surface-tertiary text-muted-strong',
                    ].join(' ')}
                  >
                    {counts[key]}
                  </span>
                  <Tabs.Indicator />
                </Tabs.Tab>
              ))}
            </Tabs.List>
          </Tabs.ListContainer>
        </div>

        <Tabs.Panel id={tab} className="flex flex-col gap-4 p-0">
          <section className="rounded-[14px] bg-surface px-4 pt-3 pb-4 shadow-surface">
            <Table variant="secondary">
              <Table.ScrollContainer className="min-[900px]:overflow-visible">
                <Table.Content aria-label={t(`tabs.${tab}`)} className="min-w-[760px]">
                  <Table.Header>
                    <Table.Column isRowHeader className={STICKY_COLUMN}>
                      {t('column.video')}
                    </Table.Column>
                    <Table.Column className={STICKY_COLUMN}>{t('column.platforms')}</Table.Column>
                    <Table.Column className={STICKY_COLUMN}>
                      {t(`column.${DETAIL_COLUMN[tab]}`)}
                    </Table.Column>
                    <Table.Column className={STICKY_COLUMN}>
                      {t(`column.${DATE_COLUMN[tab]}`)}
                    </Table.Column>
                    <Table.Column className={STICKY_COLUMN}>
                      <span className="sr-only">{t('column.actions')}</span>
                    </Table.Column>
                  </Table.Header>
                  <Table.Body
                    className="before:block before:h-1.5"
                    renderEmptyState={() => (
                      <p className="py-12 text-center text-sm text-muted">{t(`empty.${tab}`)}</p>
                    )}
                  >
                    {visible.map((row) => (
                      <Table.Row
                        key={row.key}
                        id={row.key}
                        onAction={() => void navigate(row.action.to)}
                        className="cursor-pointer"
                      >
                        <Table.Cell>
                          <span className="flex items-center gap-3">
                            <span className="grid h-9 w-16 shrink-0 place-items-center rounded-lg bg-surface-tertiary text-muted">
                              <Film className="size-4" />
                            </span>
                            <span className={`font-medium ${row.title ? '' : 'text-muted'}`}>
                              {row.title || t('screen.untitled')}
                            </span>
                          </span>
                        </Table.Cell>
                        <Table.Cell>
                          <TargetMarks marks={row.marks} />
                        </Table.Cell>
                        <Table.Cell>
                          <Chip size="sm" variant="soft" color={row.chip.tone}>
                            {row.chip.label}
                          </Chip>
                        </Table.Cell>
                        <Table.Cell className="text-[13px] whitespace-nowrap text-muted tabular-nums">
                          {formatDate(row.date)}
                        </Table.Cell>
                        <Table.Cell>
                          <span className="flex items-center justify-end gap-1">
                            {row.action.label && (
                              <Button
                                size="sm"
                                variant="tertiary"
                                onPress={() => void navigate(row.action.to)}
                              >
                                {row.action.label}
                              </Button>
                            )}
                            <Button
                              isIconOnly
                              size="sm"
                              variant="ghost"
                              aria-label={t('actions.delete')}
                              onPress={() => setPending(row)}
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </span>
                        </Table.Cell>
                      </Table.Row>
                    ))}
                  </Table.Body>
                </Table.Content>
              </Table.ScrollContainer>
            </Table>

            {rows.length > 0 && (
              <Pagination
                aria-label={t('pagination.label')}
                className="flex flex-wrap items-center justify-between gap-3 pt-4"
              >
                <Pagination.Summary className="text-[13px] text-muted tabular-nums">
                  {t('pagination.range', {
                    from: from + 1,
                    to: from + visible.length,
                    total: rows.length,
                  })}
                </Pagination.Summary>
                <Pagination.Content>
                  <Pagination.Item>
                    <Pagination.Previous
                      isDisabled={currentPage === 1}
                      onPress={() => setPage(currentPage - 1)}
                    >
                      <Pagination.PreviousIcon />
                    </Pagination.Previous>
                  </Pagination.Item>
                  {Array.from({ length: pageCount }, (_, index) => index + 1).map((number) => (
                    <Pagination.Item key={number}>
                      <Pagination.Link
                        isActive={number === currentPage}
                        onPress={() => setPage(number)}
                      >
                        {number}
                      </Pagination.Link>
                    </Pagination.Item>
                  ))}
                  <Pagination.Item>
                    <Pagination.Next
                      isDisabled={currentPage === pageCount}
                      onPress={() => setPage(currentPage + 1)}
                    >
                      <Pagination.NextIcon />
                    </Pagination.Next>
                  </Pagination.Item>
                </Pagination.Content>
                <Select
                  selectedKey={String(pageSize)}
                  onSelectionChange={(key) => {
                    setPageSize(Number(key));
                    setPage(1);
                  }}
                  className="flex-row items-center gap-2"
                >
                  <Label className="text-[13px] font-normal whitespace-nowrap text-muted">
                    {t('pagination.rowsPerPage')}
                  </Label>
                  <Select.Trigger className="w-20">
                    <Select.Value />
                    <Select.Indicator />
                  </Select.Trigger>
                  <Select.Popover>
                    <ListBox>
                      {PAGE_SIZES.map((size) => (
                        <ListBox.Item key={size} id={String(size)} textValue={String(size)}>
                          {size}
                        </ListBox.Item>
                      ))}
                    </ListBox>
                  </Select.Popover>
                </Select>
              </Pagination>
            )}
          </section>

          <ul aria-label={t('legend.label')} className="flex flex-wrap gap-5 text-xs text-muted">
            {LEGEND.map(({ key, tone }) => (
              <li key={key} className="flex items-center gap-1.5">
                <span className={`size-2.5 rounded-full ${DOT[tone]}`} />
                {t(`legend.${key}`)}
              </li>
            ))}
          </ul>
        </Tabs.Panel>
      </Tabs>

      <ConfirmDialog
        isOpen={Boolean(pending)}
        heading={
          pending?.kind === 'draft' ? t('confirm.draftHeading') : t('confirm.publicationHeading')
        }
        body={t('confirm.body', { title: pending?.title || t('screen.untitled') })}
        confirmLabel={t('actions.delete')}
        isPending={isDeletingDraft || isDeletingPublication}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPending(undefined)}
      />
    </div>
  );
}
