export interface VideoFile {
  id: string;
  path: string;
  name: string;
  size: number;
  duration?: number;
  width?: number;
  height?: number;
  mimeType: string;
  thumbnailPath?: string;
}
