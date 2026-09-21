import { Button } from '@heroui/react';
import { CalendarClock, Clapperboard, Send, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import type { RootState } from '../../app/store';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { getLabelFor } from '../../platforms/registry';

const SCHEDULE_FORMAT: Intl.DateTimeFormatOptions = {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
};

export function SummaryPanel() {
  const { t, i18n } = useTranslation('composer');
  const { video, title, publishAt, selectedPlatforms } = useSelector(
    (state: RootState) => state.composer,
  );

  const blocker = !video
    ? t('summary.needsVideo')
    : selectedPlatforms.length === 0
      ? t('summary.needsPlatform')
      : undefined;

  return (
    <aside className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-5">
      <h2 className="font-display text-lg font-semibold tracking-tight">{t('summary.title')}</h2>

      <div className="overflow-hidden rounded-xl border border-border bg-surface-secondary">
        <div className="relative aspect-video bg-surface-tertiary">
          {video?.thumbnailDataUrl ? (
            <img src={video.thumbnailDataUrl} alt="" className="size-full object-cover" />
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

      {selectedPlatforms.length > 0 && (
        <section className="flex flex-col gap-2">
          <p className="text-sm font-medium">{t('summary.platformsTitle')}</p>
          <ul className="flex flex-col gap-1.5">
            {selectedPlatforms.map((platform) => (
              <li key={platform} className="flex items-center gap-2 text-sm text-muted">
                <PlatformGlyph platform={platform} size="sm" />
                {getLabelFor(platform)}
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="flex items-center gap-2 text-sm text-muted">
        {publishAt ? (
          <>
            <CalendarClock className="size-4" />
            <span className="tabular-nums">
              {new Date(publishAt).toLocaleString(i18n.language, SCHEDULE_FORMAT)}
            </span>
          </>
        ) : (
          <>
            <Zap className="size-4" />
            {t('summary.immediate')}
          </>
        )}
      </p>

      <Button variant="primary" size="lg" fullWidth isDisabled>
        <Send className="size-4" />
        {publishAt ? t('summary.schedule') : t('summary.publish')}
      </Button>
      <p className="text-center text-xs text-muted">{blocker ?? t('summary.unavailable')}</p>
    </aside>
  );
}
