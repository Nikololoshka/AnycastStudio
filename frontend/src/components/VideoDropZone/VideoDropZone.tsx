import { useRef, useState, type DragEvent, type ReactNode } from 'react';
import { Button, ProgressBar, Spinner, Tooltip } from '@heroui/react';
import { AnimatePresence, motion } from 'motion/react';
import {
  Clapperboard,
  Clock,
  HardDrive,
  Maximize2,
  RotateCcw,
  Upload,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { clearVideo } from '../../features/composer';
import { useVideoUpload } from '../../features/upload';
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
  const { upload, start, resumeWith, cancel, dismissResume } = useVideoUpload();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [mismatch, setMismatch] = useState(false);

  const isBusy = upload.status === 'hashing' || upload.status === 'uploading';
  const resumable = upload.resumable;

  function accept(file: File | undefined) {
    if (!file || isBusy) return;
    setMismatch(false);

    if (resumable) {
      if (resumeWith(file)) return;
      setMismatch(true);
      return;
    }

    start(file);
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    setIsDragOver(false);
    accept(event.dataTransfer.files[0]);
  }

  function remove() {
    cancel();
    dispatch(clearVideo());
  }

  if (isBusy) {
    return (
      <div className="flex items-center gap-3.5 rounded-xl border border-surface-secondary bg-background p-3">
        <span className="grid h-[54px] w-24 shrink-0 place-items-center rounded-[10px] bg-surface-tertiary">
          <Spinner size="sm" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <div className="flex justify-between gap-2 text-sm">
            <span className="truncate font-medium">
              {upload.status === 'hashing' ? t('video.preparing') : t('video.uploading')}
            </span>
            <span className="shrink-0 text-muted tabular-nums">
              {t('video.sizeMegabytes', { value: megabytesOf(upload.uploadedBytes) })} /{' '}
              {t('video.sizeMegabytes', { value: megabytesOf(upload.totalBytes) })}
            </span>
          </div>
          <ProgressBar
            aria-label={t('video.uploading')}
            value={upload.percent}
            size="sm"
            className="w-full"
          >
            <ProgressBar.Track>
              <ProgressBar.Fill />
            </ProgressBar.Track>
          </ProgressBar>
          <span className="text-xs text-muted tabular-nums">{upload.percent}%</span>
        </div>
        <Tooltip delay={400}>
          <Button
            isIconOnly
            size="sm"
            variant="ghost"
            aria-label={t('video.cancelUpload')}
            onPress={cancel}
          >
            <X className="size-4" />
          </Button>
          <Tooltip.Content>{t('video.cancelUpload')}</Tooltip.Content>
        </Tooltip>
      </div>
    );
  }

  if (resumable) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-[14px] border-2 border-dashed border-border bg-background px-5 py-8 text-center">
        <RotateCcw className="size-6 text-muted" />
        <p className="font-medium">{t('video.resumeTitle', { name: resumable.filename })}</p>
        <p className="text-sm text-muted">
          {t('video.resumeHint', {
            done: megabytesOf(resumable.offset),
            total: megabytesOf(resumable.sizeBytes),
          })}
        </p>
        {mismatch && <p className="text-sm text-danger">{t('video.resumeMismatch')}</p>}
        <div className="flex gap-2">
          <Button size="sm" variant="primary" onPress={() => inputRef.current?.click()}>
            {t('video.resumeChoose')}
          </Button>
          <Button size="sm" variant="ghost" onPress={dismissResume}>
            {t('video.resumeDiscard')}
          </Button>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES}
          className="hidden"
          onChange={(event) => {
            accept(event.target.files?.[0]);
            event.target.value = '';
          }}
        />
      </div>
    );
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
          className="flex items-center gap-3.5 rounded-xl border border-surface-secondary bg-background p-3"
        >
          <div className="relative h-[54px] w-24 shrink-0 overflow-hidden rounded-[10px] bg-surface-tertiary">
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
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted">
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
            {video.mediaAssetId && <p className="mt-1 text-xs text-success">{t('video.stored')}</p>}
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
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={SWAP_TRANSITION}
          className={`group flex w-full cursor-pointer flex-col items-center justify-center gap-2.5 rounded-[14px] border-2 border-dashed px-5 py-8 text-center outline-none transition-colors focus-visible:ring-2 focus-visible:ring-focus ${
            isDragOver
              ? 'border-accent bg-accent-soft'
              : 'border-border bg-background hover:border-muted'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            className="hidden"
            onChange={(event) => {
              accept(event.target.files?.[0]);
              event.target.value = '';
            }}
          />
          <motion.span
            animate={{ y: isDragOver ? -4 : 0, scale: isDragOver ? 1.08 : 1 }}
            transition={{ type: 'spring', stiffness: 400, damping: 22 }}
            className={`grid size-11 place-items-center rounded-xl ${
              isDragOver
                ? 'bg-accent text-accent-foreground'
                : 'bg-surface-secondary text-muted-strong'
            }`}
          >
            <Upload className="size-5" />
          </motion.span>
          <span className="text-[15px] font-semibold">
            {isDragOver ? (
              t('video.release')
            ) : (
              <>
                {t('video.drop')}{' '}
                <span className="text-accent group-hover:underline">{t('video.browse')}</span>
              </>
            )}
          </span>
          <span className="text-[13px] text-muted">{t('video.formats')}</span>
          {upload.status === 'failed' && (
            <span className="text-sm text-danger">
              {t(`video.error.${upload.error}`, { defaultValue: t('video.error.unknown') })}
            </span>
          )}
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
