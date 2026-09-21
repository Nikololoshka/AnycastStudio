import type { VideoFile } from '../../domain/video/types';
import { rememberFile } from './selectedFiles';

const THUMBNAIL_SECONDS = 1;

interface VideoDetails {
  duration: number;
  width: number;
  height: number;
  thumbnailDataUrl?: string;
}

function captureFrame(video: HTMLVideoElement): string | undefined {
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext('2d');
  if (!context) return undefined;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.8);
}

function readVideoDetails(file: File): Promise<VideoDetails> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement('video');
    video.preload = 'metadata';
    video.muted = true;
    video.src = url;

    const finish = (details: VideoDetails) => {
      URL.revokeObjectURL(url);
      resolve(details);
    };

    video.onloadedmetadata = () => {
      video.currentTime = Math.min(THUMBNAIL_SECONDS, video.duration / 2);
    };

    video.onseeked = () => {
      finish({
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
        thumbnailDataUrl: captureFrame(video),
      });
    };

    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to read video metadata'));
    };
  });
}

export async function describeVideoFile(file: File): Promise<VideoFile> {
  const id = crypto.randomUUID();
  rememberFile(id, file);

  const description: VideoFile = {
    id,
    name: file.name,
    size: file.size,
    mimeType: file.type,
  };

  try {
    const details = await readVideoDetails(file);
    return { ...description, ...details };
  } catch {
    // A codec the browser cannot decode still uploads: the platform decides.
    return description;
  }
}
