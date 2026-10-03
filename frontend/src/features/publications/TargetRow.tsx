import { Button, ProgressBar } from '@heroui/react';
import { ExternalLink } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  useCancelTargetMutation,
  useRetryTargetMutation,
  type PublicationTarget,
} from '../../api/publicationsApi';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { INDETERMINATE_STATUSES } from '../../domain/publication/status';
import type { AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';

const TONE: Record<string, string> = {
  completed: 'text-success',
  scheduled: 'text-accent',
  failed: 'text-danger',
  cancelled: 'text-muted',
};

export function TargetRow({ target }: { target: PublicationTarget }) {
  const { t } = useTranslation('publications');
  const [cancel, { isLoading: isCancelling }] = useCancelTargetMutation();
  const [retry, { isLoading: isRetrying }] = useRetryTargetMutation();

  const isIndeterminate = INDETERMINATE_STATUSES.includes(target.status);
  const canRetry = target.status === 'failed' || target.status === 'cancelled';
  const canCancel = target.isActive && target.status !== 'processing';

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border px-4 py-3">
      <div className="flex items-center gap-3">
        <PlatformGlyph platform={target.platform as AvailablePlatform} size="sm" />
        <span className="font-medium">{getLabelFor(target.platform as AvailablePlatform)}</span>

        <span className={`ml-auto text-sm ${TONE[target.status] ?? 'text-muted'}`}>
          {t(`status.${target.status}`)}
        </span>

        {target.publishedUrl && (
          <a
            href={target.publishedUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
          >
            {t('actions.open')}
            <ExternalLink className="size-3.5" />
          </a>
        )}

        {canCancel && (
          <Button
            size="sm"
            variant="ghost"
            isDisabled={isCancelling}
            onPress={() => void cancel(target.id)}
          >
            {t('actions.cancel')}
          </Button>
        )}

        {canRetry && (
          <Button
            size="sm"
            variant="primary"
            isDisabled={isRetrying}
            onPress={() => void retry(target.id)}
          >
            {t('actions.retry')}
          </Button>
        )}
      </div>

      {target.isActive && (
        <ProgressBar
          aria-label={t(`status.${target.status}`)}
          value={isIndeterminate ? undefined : target.progress}
          isIndeterminate={isIndeterminate}
        />
      )}

      {target.error && (
        <p className="text-sm text-danger">
          {t(`error.${target.error.failure}`, { defaultValue: target.error.message })}
        </p>
      )}
    </div>
  );
}
