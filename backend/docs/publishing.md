# publishing

A publication and what it is doing on each platform (`backend/publishing/`).
The code says what happens; this file says why, where the reason is not
visible in the code.

## The shape

`pipeline.run_target` is a port of the desktop client's UploadManager —
validate, upload, publish, one failure recorded per target — because that
shape was right. What changed is where the state lives: Redux dispatches
became writes to the `PublicationTarget` row. The status strings are the ones
the browser speaks (`frontend/src/domain/publication/types.ts`); they are the
wire contract and do not change.

## Claiming and resuming

- A task claims its target with a conditional UPDATE before doing anything:
  SQLite has no `SKIP LOCKED`, and the claim is what turns Celery's
  at-least-once delivery (`acks_late`) into effectively-once.
- The claim takes a `queued` target, or a running one whose `last_activity_at`
  is older than `ABANDONED_AFTER` (15 minutes). Every write to the target moves
  `last_activity_at`, and a live upload writes at least once per percent, so a
  target that quiet has lost its worker. When Celery delivers the task again,
  the new worker takes it over and continues from `resume_state` and
  `uploaded_media_id` instead of re-sending the file.
- A cancel request on a target nobody runs is honoured when it is taken over.

## Never retried automatically

The Celery task has no retries (`max_retries=0`): the platform layer already
retries what is worth retrying. A failed or cancelled target is queued again
only when the person asks. Half of what makes a publication fail — a rejected
file, a revoked scope, an exhausted quota — does not improve on its own, and
each attempt spends YouTube quota that cannot be recovered. A retry keeps what
already reached the platform, so it continues rather than starts over.

## Refusing before quota is spent

- The daily limit (`User.max_publications_per_day`) refuses before Google does.
  The Data API allows roughly six uploads a day for the whole project; a
  refusal here has a reason, a 403 from Google has none anyone can act on.
- `publishAt` must carry a time zone and lie in the future. YouTube would only
  refuse it after the upload, which has already cost about 1,600 units.
- One target per platform: two YouTube targets in one publication are refused
  as invalid rather than failing on the unique constraint.

## Tokens during an upload

- A 401 in the middle of an upload forces a refresh
  (`social.services.refresh_access_token`), then the upload resumes from the
  confirmed offset. Re-reading the token is not enough: by our clock it may
  still look valid.
- A refresh that failed on the network is reported as `network`, not
  `authentication`, so the person is not told to reconnect for Google's outage.

## Scheduling

- YouTube (`native`): a scheduled video is uploaded `private`, and `publishAt`
  is sent together with `privacyStatus: private`: YouTube ignores `publishAt`
  otherwise. Nothing of ours runs at the scheduled moment.
- TikTok (`deferredUpload`): Direct Post publishes as soon as the upload ends,
  so a scheduled target stays `queued` until its time. `dispatch_due_targets`
  (Celery beat, every minute) hands it to the worker. It stamps
  `last_activity_at` with a conditional UPDATE so two sweeps do not queue it
  twice, and queues it again if no worker took it within `REDISPATCH_AFTER`.

## Confirming an asynchronous publish

TikTok accepts the file and publishes it minutes later, or refuses it. The
desktop client reported success at the end of the upload; this one does not.

- `publish` leaves the target `processing`, and `publishing.confirm_target`
  asks the platform again after 10, 30, 60, then every 120 seconds. Each task
  schedules the next, so the solo worker is never blocked while waiting.
- A confirmation claims the target optimistically on `last_activity_at`, so a
  redelivered task does nothing.
- After `CONFIRM_WITHIN_SECONDS` (30 minutes) without an answer the target
  fails, and the person is told to check the platform. It is not retried: the
  file is already there.
- If the chain is lost (a worker killed between polls), the beat sweep resumes
  it for targets silent longer than `CONFIRMATION_STALLED_AFTER`. The upload
  claim leaves `processing` targets alone, so the file is not sent twice.
- A `processing` target cannot be cancelled; the platform has the video.

## Dispatch

Targets are handed to the worker in `transaction.on_commit`, so the worker
never picks up a row that is not visible to it yet — which on SQLite it would
not be.
