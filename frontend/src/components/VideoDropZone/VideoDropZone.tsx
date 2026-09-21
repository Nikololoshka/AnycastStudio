import { useRef, useState, type DragEvent, type ReactNode } from 'react';
import { Button, Spinner, Tooltip } from '@heroui/react';
import { AnimatePresence, motion } from 'motion/react';
import {
  Clapperboard,
  Clock,
  HardDrive,
  Maximize2,
  Upload,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { clearVideo, setVideo } from '../../features/composer';
import { describeVideoFile, forgetFile } from '../../services/files';
import type { RootState } from '../../app/store';

const ACCEPTED_TYPES = 'video/*';
const SWAP_TRANSITION = { duration: 0.18 };

function megabytesOf(bytes: number): number {
  return Math.round(bytes / (1024 * 1024));
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.floor(seconds % 60);
  return `${minutes.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
}

export function VideoDropZone() {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch();
  const video = useSelector((state: RootState) => state.composer.video);
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isReading, setIsReading] = useState(false);
  const [readError, setReadError] = useState<string>();

  async function accept(file: File | undefined) {
    if (!file || isReading) return;
    setIsReading(true);
    setReadError(undefined);
    try {
      dispatch(setVideo(await describeVideoFile(file)));
    } catch {
      setReadError(t('video.readFailed'));
    } finally {
      setIsReading(false);
    }
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    setIsDragOver(false);
    void accept(event.dataTransfer.files[0]);
  }

  function remove() {
    if (video) forgetFile(video.id);
    dispatch(clearVideo());
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      {video ? (
        <motion.div
          key="selected"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={SWAP_TRANSITION}
          className="flex h-44 items-center gap-5 rounded-2xl border border-border bg-surface-secondary px-5"
        >
          <div className="relative aspect-video w-52 shrink-0 overflow-hidden rounded-xl bg-surface-tertiary">
            {video.thumbnailDataUrl ? (
              <img src={video.thumbnailDataUrl} alt="" className="size-full object-cover" />
            ) : (
              <Clapperboard className="absolute inset-0 m-auto size-6 text-muted" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium" title={video.name}>
              {video.name}
            </p>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
              <VideoFact icon={HardDrive}>
                {t('video.sizeMegabytes', { value: megabytesOf(video.size) })}
              </VideoFact>
              {video.width && video.height ? (
                <VideoFact icon={Maximize2}>
                  {video.width}×{video.height}
                </VideoFact>
              ) : null}
              {video.duration ? (
                <VideoFact icon={Clock}>{formatDuration(video.duration)}</VideoFact>
              ) : null}
            </div>
          </div>
          <Tooltip delay={400}>
            <Button
              isIconOnly
              size="sm"
              variant="ghost"
              aria-label={t('video.remove')}
              onPress={remove}
            >
              <X className="size-4" />
            </Button>
            <Tooltip.Content>{t('video.remove')}</Tooltip.Content>
          </Tooltip>
        </motion.div>
      ) : (
        <motion.button
          key="empty"
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          disabled={isReading}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={SWAP_TRANSITION}
          className={`group flex h-44 w-full cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-[1.5px] border-dashed px-6 text-center outline-none transition-colors focus-visible:ring-2 focus-visible:ring-focus ${
            isDragOver
              ? 'border-accent bg-accent/8'
              : 'border-border bg-surface-secondary/50 hover:border-muted/60'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            className="hidden"
            onChange={(event) => {
              void accept(event.target.files?.[0]);
              event.target.value = '';
            }}
          />
          <motion.span
            animate={{ y: isDragOver ? -4 : 0, scale: isDragOver ? 1.08 : 1 }}
            transition={{ type: 'spring', stiffness: 400, damping: 22 }}
            className={`grid size-12 place-items-center rounded-2xl ${
              isDragOver ? 'bg-accent text-accent-foreground' : 'bg-surface text-foreground'
            }`}
          >
            {isReading ? <Spinner size="sm" color="current" /> : <Upload className="size-5" />}
          </motion.span>
          <span className="font-display text-lg font-semibold tracking-tight">
            {isReading ? t('video.reading') : isDragOver ? t('video.release') : t('video.drop')}
          </span>
          <span className="text-sm text-muted">
            {t('video.browsePrefix')}{' '}
            <span className="font-medium text-accent group-hover:underline">
              {t('video.browse')}
            </span>
            . {t('video.formats')}
          </span>
          {readError && <span className="text-sm text-danger">{readError}</span>}
        </motion.button>
      )}
    </AnimatePresence>
  );
}

function VideoFact({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 tabular-nums">
      <Icon className="size-3.5" />
      {children}
    </span>
  );
}
