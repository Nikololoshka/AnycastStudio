import { useEffect, useRef, useState, type ReactNode } from 'react';
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
import { open } from '@tauri-apps/plugin-dialog';
import { getCurrentWebview } from '@tauri-apps/api/webview';
import { convertFileSrc } from '@tauri-apps/api/core';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { getFileMetadata } from '../../services/filesystem/FileReader';
import { clearVideo, setVideo } from '../../features/composer/composerSlice';
import type { RootState } from '../../app/store';
import type { VideoFile } from '../../domain/video/types';

function megabytesOf(bytes: number): number {
  return Math.round(bytes / (1024 * 1024));
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.floor(seconds % 60);
  return `${minutes.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`;
}

function readVideoDetails(
  path: string,
): Promise<{ duration: number; width: number; height: number; thumbnailPath: string }> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.preload = 'metadata';
    video.crossOrigin = 'anonymous';
    video.src = convertFileSrc(path);
    video.muted = true;

    video.onloadedmetadata = () => {
      video.currentTime = Math.min(1, video.duration / 2);
    };

    video.onseeked = () => {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext('2d');
      context?.drawImage(video, 0, 0, canvas.width, canvas.height);

      resolve({
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
        thumbnailPath: canvas.toDataURL('image/jpeg'),
      });
    };

    video.onerror = () => reject(new Error('Failed to read video metadata'));
  });
}

async function buildVideoFile(path: string): Promise<VideoFile> {
  const metadata = await getFileMetadata(path);
  const name = path.split(/[\\/]/).pop() ?? path;
  const details = await readVideoDetails(path);

  return {
    id: crypto.randomUUID(),
    path,
    name,
    size: metadata.size,
    mimeType: metadata.mimeType,
    duration: details.duration,
    width: details.width,
    height: details.height,
    thumbnailPath: details.thumbnailPath,
  };
}

const SWAP_TRANSITION = { duration: 0.18 };

export function VideoDropZone() {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch();
  const video = useSelector((state: RootState) => state.composer.video);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string>();
  const loadingRef = useRef(false);

  async function loadPath(path: string) {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setIsLoading(true);
    setLoadError(undefined);
    try {
      const videoFile = await buildVideoFile(path);
      dispatch(setVideo(videoFile));
    } catch {
      setLoadError(t('video.readFailed'));
    } finally {
      loadingRef.current = false;
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const unlisten = getCurrentWebview().onDragDropEvent((event) => {
      if (event.payload.type === 'over') {
        setIsDragOver(true);
      } else if (event.payload.type === 'drop') {
        setIsDragOver(false);
        const [path] = event.payload.paths;
        if (path) void loadPath(path);
      } else {
        setIsDragOver(false);
      }
    });

    return () => {
      void unlisten.then((fn) => fn());
    };
  }, []);

  async function handleChooseFile() {
    const path = await open({
      multiple: false,
      filters: [{ name: t('video.filterName'), extensions: ['mp4', 'mov', 'webm', 'avi', 'mkv'] }],
    });
    if (path) void loadPath(path);
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
            {video.thumbnailPath ? (
              <img src={video.thumbnailPath} alt="" className="size-full object-cover" />
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
              onPress={() => dispatch(clearVideo())}
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
          onClick={handleChooseFile}
          disabled={isLoading}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={SWAP_TRANSITION}
          className={`group flex w-full cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-[1.5px] border-dashed px-6 text-center h-44 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-focus ${
            isDragOver
              ? 'border-accent bg-accent/8'
              : 'border-border bg-surface-secondary/50 hover:border-muted/60'
          }`}
        >
          <motion.span
            animate={{ y: isDragOver ? -4 : 0, scale: isDragOver ? 1.08 : 1 }}
            transition={{ type: 'spring', stiffness: 400, damping: 22 }}
            className={`grid size-12 place-items-center rounded-2xl ${
              isDragOver ? 'bg-accent text-accent-foreground' : 'bg-surface text-foreground'
            }`}
          >
            {isLoading ? <Spinner size="sm" color="current" /> : <Upload className="size-5" />}
          </motion.span>
          <span className="font-display text-lg font-semibold tracking-tight">
            {isLoading ? t('video.reading') : isDragOver ? t('video.release') : t('video.drop')}
          </span>
          <span className="text-sm text-muted">
            {t('video.browsePrefix')}{' '}
            <span className="font-medium text-accent group-hover:underline">
              {t('video.browse')}
            </span>
            . {t('video.formats')}
          </span>
          {loadError && <span className="text-sm text-danger">{loadError}</span>}
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
