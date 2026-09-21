import { invoke } from '@tauri-apps/api/core';

export interface FileReader {
  size(): Promise<number>;

  read(offset: number, size: number): Promise<Uint8Array>;
}

export interface FileMetadata {
  size: number;
  mimeType: string;
}

export function getFileMetadata(path: string): Promise<FileMetadata> {
  return invoke<FileMetadata>('get_file_metadata', { path });
}

export class TauriFileReader implements FileReader {
  constructor(private readonly path: string) {}

  async size(): Promise<number> {
    const metadata = await getFileMetadata(this.path);
    return metadata.size;
  }

  async read(offset: number, size: number): Promise<Uint8Array> {
    const bytes = await invoke<number[]>('read_file_chunk', {
      path: this.path,
      offset,
      size,
    });
    return new Uint8Array(bytes);
  }
}
