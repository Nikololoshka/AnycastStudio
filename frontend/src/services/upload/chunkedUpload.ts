/**
 * Sending a video to the server, one piece at a time.
 *
 * The server is the only authority on how far a transfer got: after any
 * interruption the client asks for the offset and continues from there, rather
 * than trusting what it thinks it sent. A dropped connection costs one chunk.
 *
 * This is not an RTK Query endpoint. It is a long-running transfer with
 * progress, cancellation and resume, none of which a cache layer helps with.
 */

const API = import.meta.env.VITE_API_URL ?? '';
const RETRY_DELAYS_MS = [1_000, 2_000, 5_000, 10_000];

export interface UploadSession {
  uploadId: string;
  offset: number;
  sizeBytes: number;
  chunkSize: number;
  filename: string;
}

export interface UploadedAsset {
  id: number;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  durationSeconds: number | null;
  width: number | null;
  height: number | null;
  status: string;
  createdAt: string;
}

export interface UploadProgress {
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
}

export interface VideoDetails {
  durationSeconds?: number;
  width?: number;
  height?: number;
}

export class UploadError extends Error {
  constructor(
    readonly status: string,
    message: string,
    readonly detail?: Record<string, unknown>,
  ) {
    super(message);
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

async function call(path: string, init: RequestInit = {}): Promise<Record<string, unknown>> {
  const response = await fetch(`${API}/api${path}`, {
    credentials: 'same-origin',
    ...init,
    headers: { 'X-CSRFToken': csrfToken(), ...init.headers },
  });

  const body = await response.json().catch(() => ({ status: 'unknown' }));
  if (!response.ok) {
    throw new UploadError(body.status ?? 'unknown', body.message ?? response.statusText, body);
  }
  return body;
}

/** SHA-256 of the file, so the server can reject bytes that arrived wrong. */
export async function checksumOf(file: File): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

export async function createUpload(file: File, sha256: string): Promise<UploadSession> {
  const body = await call('/media/uploads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: file.name,
      sizeBytes: file.size,
      mimeType: file.type || 'application/octet-stream',
      sha256,
    }),
  });
  return body as unknown as UploadSession;
}

export async function readUploadStatus(uploadId: string): Promise<UploadSession> {
  return (await call(`/media/uploads/${uploadId}/status`)) as unknown as UploadSession;
}

export async function abortUpload(uploadId: string): Promise<void> {
  await call(`/media/uploads/${uploadId}/abort`, { method: 'DELETE' }).catch(() => undefined);
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new DOMException('aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}

async function sendChunk(
  uploadId: string,
  piece: Blob,
  offset: number,
  signal?: AbortSignal,
): Promise<number> {
  const response = await fetch(`${API}/api/media/uploads/${uploadId}`, {
    method: 'PATCH',
    credentials: 'same-origin',
    signal,
    headers: {
      'X-CSRFToken': csrfToken(),
      'Content-Type': 'application/octet-stream',
      'Upload-Offset': String(offset),
    },
    body: piece,
  });

  const body = await response.json().catch(() => ({ status: 'unknown' }));

  // The server and the client disagree about how much arrived. Its answer wins.
  if (response.status === 409 && typeof body.offset === 'number') {
    return body.offset;
  }
  if (!response.ok) {
    throw new UploadError(body.status ?? 'unknown', body.message ?? response.statusText, body);
  }
  return body.offset as number;
}

export interface UploadOptions {
  onProgress?: (progress: UploadProgress) => void;
  /** Called once the transfer exists, so the caller can remember how to resume it. */
  onSession?: (session: UploadSession) => void;
  signal?: AbortSignal;
  details?: VideoDetails;
  /** Continue an existing transfer instead of starting one. */
  resume?: UploadSession;
}

export async function uploadFile(file: File, options: UploadOptions = {}): Promise<UploadedAsset> {
  const { onProgress, onSession, signal, details, resume } = options;

  const sha256 = await checksumOf(file);
  const session = resume ?? (await createUpload(file, sha256));
  onSession?.(session);

  let offset = session.offset;
  let attempt = 0;

  const report = () =>
    onProgress?.({
      uploadedBytes: offset,
      totalBytes: file.size,
      percent: file.size === 0 ? 100 : Math.round((offset / file.size) * 100),
    });

  report();

  while (offset < file.size) {
    signal?.throwIfAborted();
    try {
      offset = await sendChunk(
        session.uploadId,
        file.slice(offset, offset + session.chunkSize),
        offset,
        signal,
      );
      attempt = 0;
      report();
    } catch (error) {
      if (error instanceof UploadError || signal?.aborted) throw error;
      // A network blip, not a refusal. Back off, then ask the server where it
      // actually is rather than assuming the chunk was lost.
      if (attempt >= RETRY_DELAYS_MS.length) throw error;
      await sleep(RETRY_DELAYS_MS[attempt], signal);
      attempt += 1;
      offset = (await readUploadStatus(session.uploadId)).offset;
      report();
    }
  }

  const body = await call(`/media/uploads/${session.uploadId}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(details ?? {}),
  });

  return (body as unknown as { asset: UploadedAsset }).asset;
}

/**
 * Whether a file the person just picked is the one an interrupted transfer was
 * carrying. The browser loses the File handle on reload, so resuming means
 * asking for it again — and being sure it is the same one.
 */
export function matchesSession(file: File, session: UploadSession): boolean {
  return file.size === session.sizeBytes && file.name === session.filename;
}
