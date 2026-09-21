# TikTok Content Posting API — Research Findings (Direct Post / FILE_UPLOAD)

Research-only task; no code changes proposed here. Findings below are for informing a future
TikTok adapter implementation (`src/platforms/tiktok/`, `src/services/auth/`).

## 1. OAuth redirect URI for desktop apps — loopback IS supported

Unlike the assumption that TikTok requires an HTTPS registered domain, **TikTok Login Kit does
support a loopback redirect URI** for desktop apps, similar in spirit to Google's installed-app
exception:

- Allowed hosts: only `localhost` or `127.0.0.1` (no other hostnames).
- Must include a port; wildcard port (`*`) is supported — useful since the existing YouTube
  loopback server likely picks an ephemeral port.
- Both `http` and `https` are permitted for the loopback URI.
- Max 10 redirect URIs per app, each < 512 chars, no query params or fragments.
- Valid examples: `http://localhost:3455/callback/`, `http://127.0.0.1:*/callback/`.
- PKCE is **mandatory** for desktop apps (code_verifier 43–128 chars, S256 challenge).

Source: https://developers.tiktok.com/doc/login-kit-desktop/

**Conclusion: the existing YouTube-style local loopback HTTP server pattern (`tiny_http`) is
workable for TikTok OAuth**, contrary to the initial concern in the prompt.

## 2. Token exchange still requires `client_secret` — NOT pure public-client PKCE

This is the important conflict to flag. Even though desktop apps use PKCE (`code_verifier` is
"Required for mobile and desktop app only"), TikTok's `/v2/oauth/token/` endpoint request body
requires **all** of:

- `client_key`
- `client_secret`
- `code`
- `grant_type=authorization_code`
- `redirect_uri`
- `code_verifier` (desktop/mobile only)

PKCE is additive here, not a replacement for a confidential-client secret the way it is in
Google's/most public-client OAuth designs. TikTok's desktop flow is **not** a pure public-client
PKCE-only flow.

Source: https://developers.tiktok.com/doc/oauth-user-access-token-management/

**Architectural implication (flag for human approval per CLAUDE.md Security section):** a
`client_secret` must ship with/be reachable by the desktop client to call the token endpoint.
Options to discuss with the user before implementing:
- Embed `client_secret` in the app (weak — extractable from a shipped binary, same risk class
  TikTok's own model otherwise avoids via PKCE for other platforms).
- Proxy the token exchange through a small server component the developer controls (adds a
  hosting/infra dependency, which conflicts with the "no server component" project snapshot).
- Accept the risk consciously and store the secret via the OS keyring alongside tokens (still
  extractable at build time, but avoids Redux/log/plaintext exposure).

This decision touches `src/services/auth/*` and is explicitly gated as "Human Approval Required"
under CLAUDE.md's OAuth/credential rules — do not decide unilaterally when implementing.

## 3. Sandbox / unaudited app restrictions

- An **unaudited app can post**, but content is force-restricted to **private (`SELF_ONLY`)
  visibility** regardless of the `privacy_level` requested or scopes granted.
- Sandbox: up to 5 sandboxes per app, each shareable with up to 10 TikTok accounts for testing.
- To lift the restriction to public visibility, the API client must pass TikTok's **app audit**
  for Terms of Service compliance; after audit, the account owner must also separately set their
  TikTok account to public and each post's privacy to "Everyone."
- Scopes needed:
  - `video.publish` — required for **Direct Post** (publishes straight to the creator's profile).
  - `video.upload` — required for the **upload-to-inbox** flow (draft sent to inbox; user must
    open TikTok app and manually complete/publish).
  - `user.info.basic` is a general Login Kit scope for basic profile info; the Direct Post
    reference docs found did not list it as a hard requirement for the publish call itself, only
    `video.publish`. Confirm at implementation time via the Scopes page if user info display is
    needed elsewhere in the app.
- No mention found of a distinct "target users" allowlist requirement beyond the sandbox's
  10-account cap during pre-audit testing.

Sources:
- https://developers.tiktok.com/docs/en/content-posting-api-get-started
- https://developers.tiktok.com/doc/content-sharing-guidelines

## 4. FILE_UPLOAD chunked upload mechanics

**Init call:** `POST https://open.tiktokapis.com/v2/post/publish/video/init/`

`post_info` object:
- `title` (string, max 2200 UTF-16 code units) — caption, hashtags/mentions.
- `privacy_level` (string, required) — one of `PUBLIC_TO_EVERYONE`, `MUTUAL_FOLLOW_FRIENDS`,
  `FOLLOWER_OF_CREATOR`, `SELF_ONLY`. Must be a value from that creator's
  `privacy_level_options` (fetched via the creator info query endpoint) or the publish is
  rejected. Unaudited apps are forced to `SELF_ONLY` regardless of what's sent (see §3).
- `disable_duet`, `disable_comment`, `disable_stitch` (booleans).
- `video_cover_timestamp_ms` (int32) — cover frame position; defaults to first frame.
- `brand_content_toggle` (boolean) — paid partnership disclosure.
- `brand_organic_toggle` (boolean) — creator's own business/organic promotion.
- `is_aigc` (boolean) — marks AI-generated content, adds a disclosure label.

`source_info` object (FILE_UPLOAD):
- `source: "FILE_UPLOAD"` (required)
- `video_size` (int64, required) — total file size in bytes.
- `chunk_size` (int64, required)
- `total_chunk_count` (int64, required) — `video_size / chunk_size`, rounded down.

**Response:**
- `data.publish_id` (string, max 64 chars) — tracking id for the whole lifecycle, used in the
  status-fetch call.
- `data.upload_url` (string, max 256 chars) — valid for **1 hour** after issuance.

**Chunk PUT requests** to `upload_url`:
- Required headers: `Content-Type` (`video/mp4` | `video/quicktime` | `video/webm`),
  `Content-Range: bytes {first}-{last}/{total}`, `Content-Length`.
- Chunk size: minimum 5 MB, maximum 64 MB, **except** the final chunk which may exceed
  `chunk_size` up to 128 MB to absorb the remainder.
- Files under 5 MB must be uploaded as a single chunk (no segmentation).
- Chunks must be uploaded **sequentially**.
- Max total chunks: 1000. Max total video size: **4 GB**.
- Init endpoint rate limit: 6 requests/minute per user access token.

Sources:
- https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
- https://developers.tiktok.com/doc/content-posting-api-media-transfer-guide

## 5. Post-upload status polling

Endpoint: `POST https://open.tiktokapis.com/v2/post/publish/status/fetch/`, body
`{"publish_id": "<id>"}`, `Authorization: Bearer <token>`.

Response `data` fields: `status`, `fail_reason`, `publicaly_available_post_id` (note the typo is
in TikTok's actual field name), `uploaded_bytes`, `downloaded_bytes`.

Status values observed in docs: `PROCESSING_UPLOAD` (FILE_UPLOAD in progress),
`PROCESSING_DOWNLOAD` (PULL_FROM_URL only), `SEND_TO_USER_INBOX`, `PUBLISH_COMPLETE`, `FAILED`
(inspect `fail_reason`).

- Official rate limit: **30 requests/minute** per user access token.
- TikTok's own docs did not state a single official recommended polling cadence in the pages
  fetched; secondary/community sources suggest a backoff schedule such as 10s → 30s → 60s → 120s,
  which fits comfortably under the 30/min cap. Treat the exact cadence as an implementation
  choice, not a hard TikTok requirement — just stay within 30 req/min and prefer backoff over
  fixed-interval polling since processing time scales with file size (docs/community reports:
  well under 30s for files up to ~512 MB, roughly a minute for 1 GB).

Sources:
- https://developers.tiktok.com/docs/en/content-posting-api-reference-get-video-status

## Summary of conflicts with a "Google-OAuth-like" assumption

1. **Not a conflict:** loopback redirect (`http://127.0.0.1:<port>/...`) is explicitly supported
   for desktop, so the existing YouTube-style local HTTP listener pattern transfers.
2. **Real conflict:** TikTok requires `client_secret` in the token exchange even for
   PKCE/desktop flows — it is not a public-client-only design like Google's installed-app flow.
   This needs a deliberate, human-approved decision before writing `src/services/auth/tiktok`
   (per CLAUDE.md's mandatory human-approval gate on OAuth/credential-handling changes).
3. **Practical constraint, not architecture-breaking:** unaudited apps can only publish
   `SELF_ONLY` (private) content until the app passes TikTok's audit — worth surfacing in UI/UX
   (e.g. a warning banner) rather than a blocker for building the adapter.
