# TikTok upload: diagnostics for `fail_reason: internal`

## Context

Uploading to TikTok fails reproducibly. The publication reaches 100%, then the publish status poll
returns `FAILED` with `fail_reason: internal`, and the UI shows a platform error.

Evidence collected from `%LOCALAPPDATA%\com.nikolay.scaffold\logs\multiposter.log`, four consecutive
attempts on 2026-09-20 between 20:15 and 20:39:

| File | Size / duration / resolution | `uploaded_bytes` reported by TikTok | Result |
| --- | --- | --- | --- |
| VID_20260505_163843_961.mp4 | 1477288 B, 13.7 s, 720x1280 | 1477288 | `FAILED` / `internal` |
| Ronaldo.mp4 | 8208210 B, 24.2 s, 1080x1920 | 8208210 | `FAILED` / `internal` |

What this rules out:

- **Byte transfer.** TikTok reports `uploaded_bytes` exactly equal to the file size in every attempt.
- **The video itself.** Two unrelated, valid vertical MP4s fail identically. Both satisfy the
  [Media Transfer Guide](https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide):
  resolution inside 360-4096, duration far below the 10-minute cap, size below 4 GB.
- **Chunk contract.** `compute_chunk_plan` produces a single chunk for both files. That matches the
  documented rules: files under 5 MB upload whole, `chunk_size` for Ronaldo.mp4 is 7.8 MB (inside
  5-64 MB), and `total_chunk_count = floor(video_size / chunk_size) = 1`.
- **Account permissions and post options.** The `creator_info/query` preflight returns
  `privacy_level_options: [FOLLOWER_OF_CREATOR, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY]` (so the hardcoded
  `SELF_ONLY` is allowed) and `max_video_post_duration_sec: 3600`.

What the documentation says about the reason itself, from
[Get Post Status](https://developers.tiktok.com/docs/en/content-posting-api-reference-get-video-status):

> **internal** — "Some parts of the TikTok server may currently be unavailable. This is a retryable
> error."

So `internal` is a TikTok-side failure, not a defect in the request this client builds. The user has
decided **not** to add automatic retries and **not** to add an inbox-endpoint fallback. The remaining
work is therefore purely diagnostic plus one wording correction: close the last observability gap so
that a future occurrence can be attributed without guesswork, and stop telling the user to re-encode
their video for a fault that is not theirs.

## Already applied (uncommitted working tree)

These three files are already modified and pass `npx tsc --noEmit`, `cargo check` and `npm run lint`.
They stay as they are; the plan below builds on them.

- `src/platforms/tiktok/tiktokUploadCommand.ts` — logs the full `status/fetch` response body;
  maps known `fail_reason` codes to readable messages; adds the `creator_info/query` preflight that
  validates privacy level and duration and reconciles `disable_comment` / `disable_duet` /
  `disable_stitch` against the creator's account settings.
- `src/platforms/tiktok/TikTokAdapter.ts` — passes `publication.video.duration` to the upload command
  and omits `videoCoverTimestampMs` when zero.
- `src-tauri/src/commands/tiktok_upload.rs` — `video_cover_timestamp_ms` is now `Option<u64>` and is
  only added to the init body when present.

## Change 1 — log the PUT chunk response status

`src-tauri/src/commands/tiktok_upload.rs`

This is the one remaining blind spot. The Media Transfer Guide distinguishes two success codes:

> **201 Created**: All parts uploaded; posting begins
> **206 Partial Content**: Current chunk processed; more chunks pending

`put_chunk` (around `src-tauri/src/commands/tiktok_upload.rs:229`) returns the response, and
`run_upload` discards it. `with_retry` accepts any 2xx, so a `206` on the final chunk — which would
mean TikTok is still waiting for bytes and will transcode an incomplete file — is currently
indistinguishable from a `201`.

In `run_upload`, bind the `put_chunk` result and log its status alongside the existing progress line:

```rust
let response = put_chunk(&client, &upload_url, &params.mime_type, chunk, offset, total_size).await?;
log::debug!(
    "TikTok upload {} chunk {} of {} returned status {}",
    params.upload_id,
    chunk_index + 1,
    total_chunk_count,
    response.status().as_u16()
);
```

Then, after the loop, treat a non-`201` final response as a fatal error rather than reporting the
upload as finished. Track the last status in a variable across the loop and check it once the loop
ends:

```rust
if last_status != 201 {
    return Err(UploadError::Fatal {
        message: format!(
            "TikTok did not confirm the completed upload: final chunk returned status {last_status}, expected 201"
        ),
    });
}
```

This converts a silent corruption path into an explicit, attributable failure.

## Change 2 — drop the manual `Content-Length` header

`src-tauri/src/commands/tiktok_upload.rs:241`

`put_chunk` sets `Content-Length` by hand while also passing `.body(chunk)`, and reqwest derives
`Content-Length` from a `Vec<u8>` body on its own. Remove the manual header and let reqwest set it.
The `Content-Type` and `Content-Range` headers stay — reqwest does not derive those.

## Change 3 — correct the `internal` message

`src/platforms/tiktok/tiktokUploadCommand.ts`, the `FAIL_REASON_MESSAGES` entry for `internal`

The current text advises re-encoding to H.264/AAC MP4. The evidence and the documentation both say
the video is not at fault, so that advice sends the user down a dead end. Replace it with the
documented meaning:

> TikTok's servers are temporarily unavailable; this is a retryable error on TikTok's side — try
> publishing again

Per the user's decision, the retry stays manual. No retry loop is added.

## Verification

1. `npx tsc --noEmit` and `npm run lint` — expect clean output. `VideoDropZone.tsx:127` already emits
   a pre-existing `react-hooks/exhaustive-deps` warning that is unrelated to this work.
2. `cd src-tauri && cargo check`.
3. `npm run tauri dev`, then publish Ronaldo.mp4 to TikTok and read
   `%LOCALAPPDATA%\com.nikolay.scaffold\logs\multiposter.log`. Confirm three things:
   - a `creator info: {...}` line before the upload starts;
   - a `chunk 1 of 1 returned status 201` line — a `206` here identifies the real defect;
   - the `publish status for ...` lines carrying the full response body.
4. If the run still ends in `internal` while the chunk status is `201`, the request is confirmed
   compliant end to end and the failure belongs to TikTok. The remaining lead would be the app's
   audit state: `privacy_level_options` came back without `PUBLIC_TO_EVERYONE`, which indicates an
   unaudited client. Raising that with TikTok developer support, quoting the `log_id` values from the
   status responses, is the next step — not a code change.
