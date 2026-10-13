import { useState } from 'react';
import { Button, Chip, ScrollShadow, Separator, Spinner } from '@heroui/react';
import { Plus, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { NavLink, useLocation, useNavigate } from 'react-router';
import {
  ACTIVE_POLL_MS,
  useDeleteDraftMutation,
  useDeletePublicationMutation,
  useGetDraftsQuery,
  useGetPublicationsQuery,
} from '../../api';
import type { AppDispatch } from '../../app/store';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { isAvailable, type AvailablePlatform } from '../../domain/platform/order';
import { isActiveStatus, overallStatus } from '../../domain/publication/status';
import type { PublicationStatus } from '../../domain/publication/types';
import { StorageMeter } from '../media';
import { composerReset } from '../composer';
import { uploadReset } from '../upload';

type EntryStatus = 'draft' | PublicationStatus;

interface Entry {
  kind: 'draft' | 'publication';
  id: string;
  to: string;
  title: string;
  date: string;
  platforms: AvailablePlatform[];
  status: EntryStatus;
}

const CHIP_COLOR: Partial<Record<EntryStatus, 'accent' | 'success' | 'danger' | 'warning'>> = {
  completed: 'success',
  failed: 'danger',
  scheduled: 'accent',
};

function itemClass({ isActive }: { isActive: boolean }): string {
  return [
    'flex flex-col gap-1.5 rounded-xl px-3 py-2.5 transition-colors',
    isActive ? 'bg-surface-secondary' : 'hover:bg-surface-secondary',
  ].join(' ');
}

export function PublicationsSidebar() {
  const { t, i18n } = useTranslation();
  const { t: tPublications } = useTranslation('publications');
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const { data: drafts, isLoading: isLoadingDrafts } = useGetDraftsQuery();
  const { data: publications, isLoading: isLoadingPublications } = useGetPublicationsQuery(
    undefined,
    { pollingInterval: ACTIVE_POLL_MS, skipPollingIfUnfocused: true },
  );
  const [deleteDraft, { isLoading: isDeletingDraft }] = useDeleteDraftMutation();
  const [deletePublication, { isLoading: isDeletingPublication }] = useDeletePublicationMutation();
  const [pending, setPending] = useState<Entry>();

  const entries: Entry[] = [
    ...(drafts ?? []).map((draft) => ({
      kind: 'draft' as const,
      id: draft.id,
      to: `/compose/${draft.id}`,
      title: draft.title,
      date: draft.updatedAt,
      platforms: draft.selectedPlatforms,
      status: 'draft' as const,
    })),
    ...(publications ?? []).map((publication) => ({
      kind: 'publication' as const,
      id: String(publication.id),
      to: `/publications/${publication.id}`,
      title: publication.title,
      date: publication.createdAt,
      platforms: publication.targets.map((target) => target.platform).filter(isAvailable),
      status: overallStatus(publication.targets.map((target) => target.status)),
    })),
  ].sort((a, b) => b.date.localeCompare(a.date));

  function startNew() {
    dispatch(composerReset());
    dispatch(uploadReset());
    void navigate('/compose');
  }

  async function confirmDelete() {
    if (!pending) return;
    if (pending.kind === 'draft') {
      await deleteDraft(pending.id);
    } else {
      await deletePublication(Number(pending.id));
    }
    if (pathname === pending.to) void navigate('/compose', { replace: true });
    setPending(undefined);
  }

  return (
    <aside className="hidden w-80 shrink-0 flex-col border-r border-border bg-surface lg:flex">
      <div className="p-3">
        <Button variant="primary" fullWidth onPress={startNew}>
          <Plus className="size-4" />
          {t('sidebar.new')}
        </Button>
      </div>

      <Separator />

      <ScrollShadow className="flex-1 overflow-y-auto p-2">
        {isLoadingDrafts || isLoadingPublications ? (
          <div className="grid place-items-center py-10">
            <Spinner size="sm" />
          </div>
        ) : entries.length === 0 ? (
          <p className="px-3 py-10 text-center text-sm text-muted">{t('sidebar.empty')}</p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {entries.map((entry) => (
              <li key={`${entry.kind}-${entry.id}`} className="group relative">
                <NavLink to={entry.to} className={itemClass}>
                  <span
                    className={`truncate pr-8 text-sm font-medium ${entry.title ? '' : 'text-muted'}`}
                  >
                    {entry.title || t('sidebar.untitled')}
                  </span>
                  <span className="flex items-center gap-2">
                    <Chip
                      size="sm"
                      variant="soft"
                      color={CHIP_COLOR[entry.status] ?? 'default'}
                      className={
                        entry.status !== 'draft' && isActiveStatus(entry.status) ? 'lamp-pulse' : ''
                      }
                    >
                      {entry.status === 'draft'
                        ? t('sidebar.draft')
                        : tPublications(`status.${entry.status}`)}
                    </Chip>
                    <span className="flex -space-x-1">
                      {entry.platforms.map((platform) => (
                        <PlatformGlyph key={platform} platform={platform} size="sm" />
                      ))}
                    </span>
                    <span className="ml-auto text-xs text-muted tabular-nums">
                      {new Date(entry.date).toLocaleDateString(i18n.language, {
                        day: 'numeric',
                        month: 'short',
                      })}
                    </span>
                  </span>
                </NavLink>
                <Button
                  isIconOnly
                  size="sm"
                  variant="ghost"
                  aria-label={t('sidebar.delete')}
                  className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                  onPress={() => setPending(entry)}
                >
                  <Trash2 className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </ScrollShadow>

      <Separator />

      <div className="p-4">
        <StorageMeter />
      </div>

      <ConfirmDialog
        isOpen={Boolean(pending)}
        heading={
          pending?.kind === 'draft'
            ? t('sidebar.confirm.draftHeading')
            : t('sidebar.confirm.publicationHeading')
        }
        body={t('sidebar.confirm.body', { title: pending?.title || t('sidebar.untitled') })}
        confirmLabel={t('sidebar.delete')}
        isPending={isDeletingDraft || isDeletingPublication}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPending(undefined)}
      />
    </aside>
  );
}
