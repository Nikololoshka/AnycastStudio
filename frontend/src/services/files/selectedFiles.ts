/**
 * Holds the `File` objects the person picked.
 *
 * A File cannot live in Redux: it is not serializable, and the browser drops
 * the handle on reload anyway. The store keeps the description of the video;
 * this keeps the bytes, keyed by the same id, for as long as the tab lives.
 */

const files = new Map<string, File>();

export function rememberFile(id: string, file: File): void {
  files.set(id, file);
}

export function getFile(id: string): File | undefined {
  return files.get(id);
}

export function forgetFile(id: string): void {
  files.delete(id);
}
