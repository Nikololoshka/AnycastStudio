import { Meter, Skeleton } from '@heroui/react';
import { HardDrive } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useGetMediaAssetsQuery } from '../../api';
import { formatBytes } from './formatBytes';

function colorOf(ratio: number) {
  return ratio >= 0.95 ? 'danger' : ratio >= 0.8 ? 'warning' : 'accent';
}

export function StorageMeter() {
  const { t, i18n } = useTranslation('media');
  const { data } = useGetMediaAssetsQuery();

  if (!data) return <Skeleton className="h-10 rounded-lg" />;

  const ratio = data.quotaBytes > 0 ? data.usedBytes / data.quotaBytes : 0;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-xs text-muted">
        <HardDrive className="size-3.5" />
        <span>{t('storage.title')}</span>
        <span className="ml-auto tabular-nums">
          {t('storage.usage', {
            used: formatBytes(data.usedBytes, i18n.language),
            quota: formatBytes(data.quotaBytes, i18n.language),
          })}
        </span>
      </div>
      <Meter
        aria-label={t('storage.title')}
        value={data.usedBytes}
        maxValue={Math.max(data.quotaBytes, 1)}
        color={colorOf(ratio)}
        size="sm"
      >
        <Meter.Track>
          <Meter.Fill />
        </Meter.Track>
      </Meter>
    </div>
  );
}
