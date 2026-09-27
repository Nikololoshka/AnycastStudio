# media

Uploaded video and the chunked transfer that produces it (`backend/media/`).
The code says what happens; this file says why, where the reason is not
visible in the code.

## The transfer

The browser sends a large file in pieces, the same resumable shape the
platforms use: `start` returns an upload id and the chunk size, each `PATCH`
carries `Upload-Offset`, `status` says where to continue, `complete` verifies
and turns the transfer into an asset. A dropped connection costs one chunk, not
the whole file.

- The chunk size is the server's decision (`UPLOAD_CHUNK_BYTES`), so it can be
  tuned without releasing a new frontend.
- The server is the only authority on the offset. A chunk at any other offset
  is answered `conflict` with the real one.
- A chunk is written **at its offset**, not appended, and `received_bytes`
  moves with a conditional UPDATE (`received_bytes = offset`). A client that
  repeats a chunk while the first copy is still being written — a timeout
  retry — overwrites the same bytes with the same bytes and is then told the
  real offset, instead of appending a second copy. The `sha256` is optional,
  so without this a corrupted file could go all the way to YouTube.
- The body is read in 256 KiB pieces from the request stream, never through
  `request.body`, and never more than one byte past the declared size: a
  chunk is megabytes, and one oversized request must not be able to fill the
  disk before it is refused.
- `complete` claims the transfer with a conditional UPDATE (`open` →
  `completed`) before doing anything, so two completions cannot both create an
  asset. The checksum is computed in one pass at the end: hashlib state cannot
  be persisted between requests, and one sequential read of a few gigabytes is
  cheaper than the machinery to avoid it.
- Open transfers count against the storage quota by what they already wrote,
  so ten uploads that only together exceed it cannot all start.

## Storage

- Every path is built in `storage.py` and nowhere else, so moving to object
  storage later is a change to one module.
- A transfer in progress lives in `uploads/<id>.part`, outside the person's
  folder: it is not their file until it is complete and verified.
- Deleting a file also removes its per-asset folder once empty, but never the
  person's folder or the root.

## When a file is deleted

A file is deleted only when nothing can need it again:

- never used by a publication, and older than `ORPHAN_ASSET_TTL_HOURS`;
- used by publications whose targets have all finished, and the last one
  finished more than `MEDIA_RETENTION_HOURS` ago — long enough to retry a
  failed target.

While any target of a publication has no `finished_at` (queued, uploading,
retried), the file stays, and a person's request to delete it is answered
`conflict` / `asset_in_use`. On Windows an open file cannot be deleted at all,
so this also keeps the pipeline from a `PermissionError`.

These rules read the publications through reverse relations
(`publications__targets__finished_at`) rather than importing `publishing`, so
the dependency still runs from `publishing` to `media` only.

The row itself is kept with the status `deleted`: `Publication.asset` is
`PROTECT`, and the history keeps pointing at it.
