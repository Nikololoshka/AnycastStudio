import { useState } from 'react';
import { Button, Card, Spinner, Table, Tooltip } from '@heroui/react';
import { Inbox, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDeleteMediaAssetMutation, useGetMediaAssetsQuery, type MediaAsset } from '../../api';
import { messageOf, statusOf } from '../../api/errors';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { formatBytes } from './formatBytes';
import { StorageMeter } from './StorageMeter';

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.floor(seconds % 60);
  return `${minutes.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
}

export function FilesScreen() {
  const { t, i18n } = useTranslation('media');
  const { data, isLoading } = useGetMediaAssetsQuery();
  const [deleteAsset, { isLoading: isDeleting }] = useDeleteMediaAssetMutation();
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
          ? t('files.error.inUse', { name: pending.filename })
          : (messageOf(cause) ?? t('files.error.unknown')),
      );
    }
    setPending(undefined);
  }

  if (isLoading) {
    return (
      <div className="grid place-items-center py-16">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">{t('files.title')}</h1>
          <p className="mt-1 text-sm text-muted">{t('files.subtitle')}</p>
        </div>
        <div className="w-72">
          <StorageMeter />
        </div>
      </header>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      {data?.assets.length ? (
        <Table>
          <Table.ScrollContainer>
            <Table.Content aria-label={t('files.title')}>
              <Table.Header>
                <Table.Column isRowHeader>{t('files.column.name')}</Table.Column>
                <Table.Column>{t('files.column.size')}</Table.Column>
                <Table.Column>{t('files.column.duration')}</Table.Column>
                <Table.Column>{t('files.column.resolution')}</Table.Column>
                <Table.Column>{t('files.column.uploaded')}</Table.Column>
                <Table.Column>
                  <span className="sr-only">{t('files.delete')}</span>
                </Table.Column>
              </Table.Header>
              <Table.Body>
                {data.assets.map((asset) => (
                  <Table.Row key={asset.id} id={asset.id}>
                    <Table.Cell className="max-w-96 truncate font-medium">
                      {asset.filename}
                    </Table.Cell>
                    <Table.Cell className="tabular-nums">
                      {formatBytes(asset.sizeBytes, i18n.language)}
                    </Table.Cell>
                    <Table.Cell className="tabular-nums">
                      {asset.durationSeconds === null ? '—' : formatDuration(asset.durationSeconds)}
                    </Table.Cell>
                    <Table.Cell className="tabular-nums">
                      {asset.width && asset.height ? `${asset.width}×${asset.height}` : '—'}
                    </Table.Cell>
                    <Table.Cell className="tabular-nums text-muted">
                      {new Date(asset.createdAt).toLocaleString(i18n.language)}
                    </Table.Cell>
                    <Table.Cell className="text-right">
                      <Tooltip delay={400}>
                        <Button
                          isIconOnly
                          size="sm"
                          variant="ghost"
                          aria-label={t('files.delete')}
                          onPress={() => setPending(asset)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                        <Tooltip.Content>{t('files.delete')}</Tooltip.Content>
                      </Tooltip>
                    </Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Content>
          </Table.ScrollContainer>
        </Table>
      ) : (
        <Card>
          <Card.Content className="flex flex-col items-center gap-3 py-12 text-center">
            <Inbox className="size-8 text-muted" />
            <p className="text-sm text-muted">{t('files.empty')}</p>
          </Card.Content>
        </Card>
      )}

      <ConfirmDialog
        isOpen={Boolean(pending)}
        heading={t('files.confirm.heading')}
        body={t('files.confirm.body', { name: pending?.filename ?? '' })}
        confirmLabel={t('files.delete')}
        isPending={isDeleting}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPending(undefined)}
      />
    </div>
  );
}
