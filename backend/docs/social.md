# social

Connected platform accounts and the OAuth flow that creates them
(`backend/social/`). The code says what happens; this file says why, where the
reason is not visible in the code.

## Connecting

- `sessions.create` starts an `OAuthSession` with a random `state` and, for
  PKCE platforms, a verifier that is stored encrypted and never leaves the
  server. Expired sessions are swept whenever a new one starts.
- The callback is a GET the platform redirects to, so it cannot carry a CSRF
  token. `state` is the defence, and it is checked twice: that we issued it and
  it is still pending (`sessions.claim`), and that it belongs to the person
  whose session cookie is on the request. Without the second check a stranger
  could graft their own platform account onto someone else's tenant.
- `claim` is a conditional UPDATE, not a lock: SQLite has no
  `SELECT ... FOR UPDATE SKIP LOCKED`, and the pattern ports unchanged to
  PostgreSQL. Two callbacks carrying the same `state` cannot both proceed.
- The callback catches every exception and only logs it: a traceback in the
  browser could show the token exchange, which carries `client_secret`.

## Keeping tokens usable

- A token is refreshed `REFRESH_MARGIN` (5 minutes) before it expires, so a
  request that starts now does not end with a token that died mid-upload.
- The periodic task (`social.refresh_expiring_tokens`, every 30 minutes)
  refreshes anything expiring within the hour, so a publication rarely waits
  for a refresh and a revoked grant is noticed before the person presses
  Publish.
- A refresh never holds a transaction open across the call to the platform
  (SQLite rule 1): read the row, call the platform, then write with a
  conditional UPDATE on `token_expires_at`. If another caller refreshed first,
  the UPDATE touches nothing and the row is re-read.
- Only one caller refreshes an account at a time. It first claims
  `refresh_lease_until` with a conditional UPDATE; X and TikTok rotate refresh
  tokens, so a second simultaneous call would burn the winner's token. A caller
  that loses the claim polls the row until the token changes or the lease is
  released, then uses the new token. If the other refresh never finishes, it
  gets a transient error and the account stays `active`. A lease lasts
  `REFRESH_LEASE` (2 minutes), so a worker killed mid-refresh does not block
  the account for longer than that.
- Only a refusal (`invalid_grant`, a missing refresh token) marks the account
  `needs_reauth`. A transient failure (network, 5xx after the retries) is
  raised as it is and leaves the account `active`.

## Disconnecting

- The refresh token is revoked at the platform once, best effort, from the
  request itself. It is not handed to Celery: the task message would put the
  token in Redis in clear text.
- The row is kept, with its tokens erased and the status `revoked`:
  `PublicationTarget.social_account` is `PROTECT`, so the publication history
  keeps pointing at it. Revoked accounts are not listed and cannot be
  disconnected twice. Connecting the same channel again revives the row.

## Tokens stay on the server

- Tokens are `EncryptedTextField`s. They never appear in `account_json`, in
  `__str__` (which reaches logs and the admin), or in the admin, where they are
  excluded rather than read-only so no decrypted token is rendered into HTML.
