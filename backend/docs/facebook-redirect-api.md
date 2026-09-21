# API

Base URL: `https://nikololoshka-fileserver.online`

The service runs the OAuth sign-in for the desktop app. The app never sees the provider's client secret or the authorization code; it gets only the final access token.

Only known clients can use the API: `/start` requires a **client token**, issued by the server operator and sent as `Authorization: Bearer <client token>`. `/poll` is authorized by the per-login `poll_token` instead.

Supported providers: `facebook`. Every provider has the same three endpoints under `/multiposter/auth_<provider>/`.

| Method | Path | Called by |
| --- | --- | --- |
| `POST` | `/multiposter/auth_facebook/start` | Desktop app |
| `GET` | `/multiposter/auth_facebook/callback` | Facebook (browser redirect), not the app |
| `POST` | `/multiposter/auth_facebook/poll` | Desktop app |

## Response format

Every response from `/start` and `/poll`, and every API error, is a JSON object with a top-level `status` string. Branch on `status`; the HTTP code always matches it, and the other fields depend on it.

| `status` | HTTP | Returned by | Extra fields |
| --- | --- | --- | --- |
| `ok` | 200 | `/start` | `auth_url`, `poll_token`, `expires_in` |
| `pending` | 200 | `/poll` | none |
| `done` | 200 | `/poll` | `provider`, `access_token`, `token_type`, `expires_in` |
| `error` | 200 | `/poll` | `error`, and `error_reason` or `message` |
| `unauthorized` | 401 | `/start`, `/poll` | none |
| `not_found` | 404 | `/poll`, any unknown path or provider | none |
| `method_not_allowed` | 405 | `/start`, `/poll` with a method other than `POST` | none |
| `expired` | 410 | `/poll` | none |
| `rate_limited` | 429 | `/start`, `/poll` | none |
| `server_error` | 500 | any endpoint | none |

`error` means the sign-in itself failed (the user cancelled, the provider refused); every other non-`ok`/`pending`/`done` status is a problem with the request or the session.

## Flow

1. The app calls `POST /start` with its client token and gets `auth_url` and `poll_token`.
2. The app opens `auth_url` in the user's browser.
3. The user signs in with Facebook. Facebook redirects the browser to `/callback`; the server exchanges the code for a token and shows a "you can close this window" page.
4. Meanwhile the app calls `POST /poll` with the `poll_token` in a loop until the status is not `pending`.
5. `/poll` returns the access token (`status: "done"`) or an error (`status: "error"`). The result is returned **once**; after that the session is deleted.

A session lives for **600 s** (10 minutes) after `/start`. After that the callback link is rejected and `/poll` returns `410 expired`.

## POST /multiposter/auth_facebook/start

Creates an auth session. No body is required. The client token goes in the `Authorization` header only; it is not accepted in the URL or body.

```bash
curl -X POST https://nikololoshka-fileserver.online/multiposter/auth_facebook/start   -H "Authorization: Bearer <client token>"
```

**200 OK**

```json
{
  "status": "ok",
  "auth_url": "https://www.facebook.com/v23.0/dialog/oauth?client_id=...&redirect_uri=...&state=...&response_type=code&scope=public_profile%2Cemail",
  "poll_token": "p7w0Hk...43 chars...",
  "expires_in": 600
}
```

| Field | Description |
| --- | --- |
| `status` | Always `ok`. |
| `auth_url` | Open this in the system browser. |
| `poll_token` | Secret for `/poll`. Keep it in memory only; do not log it or put it in URLs. |
| `expires_in` | Session lifetime in seconds. |

**401 Unauthorized**: `{"status": "unauthorized"}`. The client token is missing, wrong or sent another way than `Authorization: Bearer`. Do not retry; the app needs a valid token.

**429 Too Many Requests**: `{"status": "rate_limited"}`. Limit: 10 requests per minute per IP, counted before the token check.

## POST /multiposter/auth_facebook/poll

Long-poll for the sign-in result. The server holds the request for up to **25 s** and answers as soon as the result is ready. If nothing happens in 25 s, it answers `pending`; call it again right away.

Use an HTTP client timeout **above 25 s** (for example 40 s).

The token goes in the `Authorization` header only. It is not accepted in the URL or body.

```bash
curl -X POST https://nikololoshka-fileserver.online/multiposter/auth_facebook/poll \
  -H "Authorization: Bearer <poll_token>" \
  --max-time 40
```

### Responses

| HTTP | `status` | Meaning | What to do |
| --- | --- | --- | --- |
| 200 | `pending` | The user has not finished yet. | Poll again. |
| 200 | `done` | Sign-in succeeded; the token is in the body. | Stop. Save the token. |
| 200 | `error` | Sign-in was cancelled or failed; see `error`. | Stop. Show the error, offer to retry from `/start`. |
| 401 | `unauthorized` | The `Authorization: Bearer` header is missing or empty. | Fix the request. |
| 404 | `not_found` | Unknown token, or the result was already handed out. | Stop. Start over. |
| 405 | `method_not_allowed` | The request was not a `POST`. | Fix the request. |
| 410 | `expired` | The session is older than 600 s. | Stop. Start over. |
| 429 | `rate_limited` | More than 120 requests per minute from this IP. | Wait a few seconds, then poll again. |
| 500 | `server_error` | Unexpected server error. | Wait, then poll again. |

**done**

```json
{
  "status": "done",
  "provider": "facebook",
  "access_token": "EAAB...",
  "token_type": "bearer",
  "expires_in": 5183944
}
```

`expires_in` is the token lifetime in seconds as reported by Facebook; it can be `null`.

**error**

```json
{
  "status": "error",
  "error": "access_denied",
  "error_reason": "user_denied"
}
```

Possible `error` values:

| `error` | Cause | Extra fields |
| --- | --- | --- |
| `access_denied` (or another value from Facebook) | The user cancelled the login, or Facebook returned an error to the callback. | `error_reason` (optional) |
| `missing_code` | Facebook redirected back without a code or an error. | none |
| `facebook_error` | Exchanging the code for a token failed. | `message`: human-readable reason |
| `server_error` | Unexpected server error. | none |

## GET /multiposter/auth_facebook/callback

Not called by the app. Facebook redirects the browser here with `code` and `state` (or `error`, `error_reason`). The server shows a short page in Russian:

| HTTP | Page | When |
| --- | --- | --- |
| 200 | "Готово" (done) | Token received; `/poll` will return `done`. |
| 200 | "Вход отменён" (cancelled) | The user cancelled; `/poll` will return `error`. |
| 502 / 500 | "Не удалось войти" (failed) | Token exchange failed; `/poll` will return `error`. |
| 400 | "Ссылка недействительна" (invalid link) | Unknown, expired or already used `state`. |

This endpoint answers with HTML pages, not JSON.

## Other errors

- Wrong HTTP method (for example `GET /start`): **405** `{"status": "method_not_allowed"}` with an `Allow: POST` header.
- Unknown path or provider: **404** `{"status": "not_found"}`.
- Unexpected server error: **500** `{"status": "server_error"}`.

## Client example (Python)

```python
import time
import webbrowser

import requests

BASE = "https://nikololoshka-fileserver.online/multiposter/auth_facebook"
CLIENT_TOKEN = "..."  # issued by the server operator


def facebook_login() -> str:
    client_auth = {"Authorization": f"Bearer {CLIENT_TOKEN}"}
    data = requests.post(f"{BASE}/start", headers=client_auth, timeout=10).json()
    if data["status"] != "ok":
        raise RuntimeError(f"Could not start login: {data['status']}")

    webbrowser.open(data["auth_url"])
    headers = {"Authorization": f"Bearer {data['poll_token']}"}

    while True:
        try:
            response = requests.post(f"{BASE}/poll", headers=headers, timeout=40)
        except requests.Timeout:
            continue
        result = response.json()
        status = result["status"]

        if status == "pending":
            continue
        if status in ("rate_limited", "server_error"):
            time.sleep(5)
            continue
        if status == "done":
            return result["access_token"]
        if status == "error":
            raise RuntimeError(result.get("message") or result["error"])
        raise RuntimeError(f"Login failed: {status}")  # not_found, expired, unauthorized, method_not_allowed
```

## Notes

- The client token is shipped inside the desktop app, so treat it as a way to keep casual callers out, not as a strong secret. The operator can rotate it: the server accepts several tokens at once, so a new app version can switch before the old token is removed.
- The session ends on its own after 600 s, so the app should stop polling by then (it will get `410 expired`).
- Each `/start` creates a new session. Starting again does not cancel the previous one; it simply expires.
- Only one `/poll` call gets a finished result. If two run at once, the other gets `404 not_found`.
