export interface VideoFile {
  id: string;
  name: string;
  size: number;
  mimeType: string;

  duration?: number;
  width?: number;
  height?: number;

  /** A frame grabbed in the browser, as a data URL. */
  thumbnailDataUrl?: string;

  /** Set once the bytes have reached the server. */
  mediaAssetId?: string;
}
