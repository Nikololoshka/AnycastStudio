import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { matchesSession, uploadFile, type UploadSession } from './chunkedUpload';

const CHUNK_SIZE = 4;
const CONTENT = 'abcdefghij'; // 10 bytes, three chunks of 4 and a tail of 2

function fileOf(text = CONTENT, name = 'clip.mp4'): File {
  return new File([text], name, { type: 'video/mp4' });
}

function sessionOf(offset = 0, size = CONTENT.length): UploadSession {
  return {
    uploadId: 'upload-1',
    offset,
    sizeBytes: size,
    chunkSize: CHUNK_SIZE,
    filename: 'clip.mp4',
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => body,
  } as Response;
}

/** A server that accepts everything it is sent and tracks the offset itself. */
function fakeServer(startAt = 0) {
  const received: string[] = [];
  let offset = startAt;

  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/media/uploads')) {
      return jsonResponse(200, sessionOf());
    }
    if (url.endsWith('/complete')) {
      return jsonResponse(200, { status: 'ok', asset: { id: 7, sizeBytes: offset } });
    }
    if (url.endsWith('/status')) {
      return jsonResponse(200, { ...sessionOf(offset) });
    }

    const body = init?.body as Blob;
    received.push(await body.text());
    offset += body.size;
    return jsonResponse(200, { status: 'ok', offset });
  });

  return { fetchMock, received, offsetNow: () => offset };
}

describe('uploadFile', () => {
  beforeEach(() => {
    vi.stubGlobal('document', { cookie: 'csrftoken=abc' });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends the whole file in chunks of the size the server asked for', async () => {
    const server = fakeServer();
    vi.stubGlobal('fetch', server.fetchMock);

    await uploadFile(fileOf());

    expect(server.received).toEqual(['abcd', 'efgh', 'ij']);
  });

  it('reports progress that ends at a hundred per cent', async () => {
    const server = fakeServer();
    vi.stubGlobal('fetch', server.fetchMock);
    const percentages: number[] = [];

    await uploadFile(fileOf(), { onProgress: ({ percent }) => percentages.push(percent) });

    expect(percentages[0]).toBe(0);
    expect(percentages[percentages.length - 1]).toBe(100);
  });

  it('starts from the offset of a resumed transfer instead of the beginning', async () => {
    // The server already holds the first four bytes.
    const server = fakeServer(4);
    vi.stubGlobal('fetch', server.fetchMock);

    await uploadFile(fileOf(), { resume: sessionOf(4) });

    // The first four bytes already reached the server and are not sent again.
    expect(server.received).toEqual(['efgh', 'ij']);
  });

  it('never asks the server to create a session when resuming', async () => {
    const server = fakeServer(4);
    vi.stubGlobal('fetch', server.fetchMock);

    await uploadFile(fileOf(), { resume: sessionOf(4) });

    const created = server.fetchMock.mock.calls.filter(([url]) =>
      String(url).endsWith('/media/uploads'),
    );
    expect(created).toHaveLength(0);
  });

  it('follows the offset the server reports on a conflict', async () => {
    // The client thinks it is at 0; the server already holds 8 bytes, which is
    // what happens when a connection drops after the write but before the reply.
    const sent: string[] = [];
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/complete')) return jsonResponse(200, { asset: { id: 7 } });
      const body = init?.body as Blob;
      if (sent.length === 0) {
        sent.push(await body.text());
        return jsonResponse(409, { status: 'conflict', offset: 8 });
      }
      sent.push(await body.text());
      return jsonResponse(200, { status: 'ok', offset: 10 });
    });
    vi.stubGlobal('fetch', fetchMock);

    await uploadFile(fileOf(), { resume: sessionOf(0) });

    expect(sent).toEqual(['abcd', 'ij']);
  });

  it('hands back the asset the server created', async () => {
    const server = fakeServer();
    vi.stubGlobal('fetch', server.fetchMock);

    const asset = await uploadFile(fileOf());

    expect(asset.id).toBe(7);
  });

  it('reports the session id so an interrupted transfer can be found again', async () => {
    const server = fakeServer();
    vi.stubGlobal('fetch', server.fetchMock);
    const seen: string[] = [];

    await uploadFile(fileOf(), { onSession: (session) => seen.push(session.uploadId) });

    expect(seen).toEqual(['upload-1']);
  });

  it('stops when the signal is aborted', async () => {
    const server = fakeServer();
    vi.stubGlobal('fetch', server.fetchMock);
    const abort = new AbortController();
    abort.abort();

    await expect(uploadFile(fileOf(), { signal: abort.signal })).rejects.toThrow();
  });

  it('gives up on a refusal rather than retrying it', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith('/media/uploads')) return jsonResponse(200, sessionOf());
      return jsonResponse(409, { status: 'quota_exceeded' });
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(uploadFile(fileOf())).rejects.toThrow();
  });
});

describe('matchesSession', () => {
  it('accepts the file the transfer was carrying', () => {
    expect(matchesSession(fileOf(), sessionOf())).toBe(true);
  });

  it('rejects a file of a different size', () => {
    expect(matchesSession(fileOf('abc'), sessionOf())).toBe(false);
  });

  it('rejects a file with a different name', () => {
    expect(matchesSession(fileOf(CONTENT, 'other.mp4'), sessionOf())).toBe(false);
  });
});
