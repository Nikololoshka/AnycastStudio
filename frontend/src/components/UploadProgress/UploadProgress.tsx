import type { ReactNode } from 'react';
import { Button, ProgressBar } from '@heroui/react';
import { CalendarClock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import type { PublicationError, PublicationStatus } from '../../domain/publication/types';
import { INDETERMINATE_STATUSES } from '../../domain/publication/status';
import { ROUTE_LINE_CLASSES, routeToneOf, type RouteTone } from './routeTone';
import { PlatformGlyph } from '../PlatformGlyph';

export interface UploadProgressProps {
  platform: AvailablePlatform;
  status: PublicationStatus;
  percent?: number;
  error?: PublicationError;
  accountName?: string;
  scheduledAt?: string;
  isEnabled?: boolean;
  leadTone?: RouteTone;
  trailTone?: RouteTone;
  onToggle?: () => void;
  onCancelSchedule?: () => void;
}

const SCHEDULED_TIME_FORMAT: Intl.DateTimeFormatOptions = {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
};

type Tone = RouteTone;

const LAMP_CLASSES: Record<Tone, string> = {
  off: 'ring-1 ring-inset ring-border',
  idle: 'ring-1 ring-inset ring-muted',
  active: 'bg-accent lamp-pulse',
  success: 'bg-success',
  danger: 'bg-danger',
};

const STATUS_TEXT_CLASSES: Record<Tone, string> = {
  off: 'text-muted',
  idle: 'text-muted',
  active: 'text-accent',
  success: 'text-success',
  danger: 'text-danger',
};

function Row({
  onToggle,
  isEnabled,
  label,
  children,
}: {
  onToggle?: () => void;
  isEnabled: boolean;
  label: string;
  children: ReactNode;
}) {
  const className = `flex w-full items-center gap-3 rounded-xl px-2 py-2 -mx-2 text-left transition-colors ${
    isEnabled ? '' : 'opacity-55'
  }`;

  if (!onToggle) return <div className={className}>{children}</div>;

  return (
    <button
      type="button"
      aria-pressed={isEnabled}
      aria-label={label}
      onClick={onToggle}
      className={`${className} cursor-pointer hover:bg-surface-tertiary hover:opacity-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent`}
    >
      {children}
    </button>
  );
}

export function UploadProgress({
  platform,
  status,
  percent,
  error,
  accountName,
  scheduledAt,
  isEnabled = true,
  leadTone = 'off',
  trailTone = 'off',
  onToggle,
  onCancelSchedule,
}: UploadProgressProps) {
  const { t, i18n } = useTranslation('composer');
  const tone = routeToneOf(status, isEnabled);
  const isIndeterminate = INDETERMINATE_STATUSES.includes(status);
  const showsBar = tone === 'active' || (isEnabled && status === 'completed');
  const value = percent ?? 0;

  return (
    <li className="group/route relative pl-9">
      <span
        aria-hidden
        className={`absolute top-[25px] -bottom-px left-3 border-l-[1.5px] transition-colors duration-500 group-last/route:hidden ${ROUTE_LINE_CLASSES[trailTone]}`}
      />
      <span
        aria-hidden
        className={`absolute -top-px left-3 h-[27px] w-6 rounded-bl-xl border-b-[1.5px] border-l-[1.5px] transition-colors duration-500 ${ROUTE_LINE_CLASSES[tone]}`}
      />
      <span
        aria-hidden
        className={`absolute -top-px left-3 ${trailTone === 'off' ? 'h-[15px]' : 'h-[27px]'} border-l-[1.5px] transition-colors duration-500 ${ROUTE_LINE_CLASSES[leadTone]}`}
      />
      <Row
        onToggle={onToggle}
        isEnabled={isEnabled}
        label={t(isEnabled ? 'progress.disable' : 'progress.enable', {
          platform: getLabelFor(platform),
        })}
      >
        <PlatformGlyph platform={platform} size="md" className={isEnabled ? '' : 'grayscale'} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className={`font-medium ${isEnabled ? '' : 'text-muted'}`}>
              {getLabelFor(platform)}
            </span>
            <span
              className={`flex items-center gap-1.5 text-xs font-medium tabular-nums ${STATUS_TEXT_CLASSES[tone]}`}
            >
              <span className={`size-1.5 rounded-full ${LAMP_CLASSES[tone]}`} />
              {isEnabled ? t(`progress.status.${status}`) : t('progress.off')}
              {isEnabled && status === 'uploading' && ` ${t('progress.percent', { value })}`}
            </span>
          </div>
          <p className="truncate text-xs text-muted">
            {accountName ?? t('status.none', { ns: 'accounts' })}
          </p>
        </div>
      </Row>

      {showsBar && (
        <div className="pb-1">
          <ProgressBar
            aria-label={t('progress.barLabel', { platform: getLabelFor(platform) })}
            value={isIndeterminate ? undefined : value}
            isIndeterminate={isIndeterminate}
            size="sm"
            color={status === 'completed' ? 'success' : 'accent'}
          >
            <ProgressBar.Track>
              <ProgressBar.Fill />
            </ProgressBar.Track>
          </ProgressBar>
        </div>
      )}

      {isEnabled && status === 'scheduled' && scheduledAt && (
        <div className="flex items-center justify-between gap-2 pb-2 text-xs text-muted">
          <span className="flex min-w-0 items-center gap-2">
            <CalendarClock className="size-3.5 shrink-0" />
            <span className="truncate tabular-nums">
              {t('progress.scheduledFor', {
                time: new Date(scheduledAt).toLocaleString(i18n.language, SCHEDULED_TIME_FORMAT),
              })}
            </span>
          </span>
          {onCancelSchedule && (
            <Button
              size="sm"
              variant="ghost"
              onPress={onCancelSchedule}
              aria-label={t('progress.cancelSchedule', { platform: getLabelFor(platform) })}
            >
              {t('progress.cancel')}
            </Button>
          )}
        </div>
      )}

      {isEnabled && error && (
        <p className="pb-2 text-xs break-words text-danger">
          {t(`errors.${error.type}`)}
          {': '}
          {error.message}
        </p>
      )}
    </li>
  );
}
