export interface VideoFile {
  id: string;
  name: string;
  size: number;
  mimeType: string;

  duration?: number;
  width?: number;
  height?: number;

  /** A frame grabbed in the browser as a data URL, or the server's copy of it. */
  thumbnailUrl?: string;

  /** Set once the bytes have reached the server. */
  mediaAssetId?: string;
}
