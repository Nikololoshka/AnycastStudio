---
paths:
  - "backend/social/**"
  - "backend/platforms/core/auth/**"
  - "backend/platforms/*/auth/**"
  - "backend/services/usecases/accounts/**"
  - "backend/common/encryption/**"
---

# Backend social accounts and credentials

Ask the human before changing anything in these paths: a mistake here leaks
tokens or lets one user act as another.

- Platform tokens live only in `SocialAccount`, encrypted with
  `EncryptedTextField`.
- Log a network exception's class, never its text: it contains the URL and
  `client_secret`. Keep the `aiohttp` logger at WARNING.
- Check OAuth `state` twice: we issued it and it is still pending, and it
  belongs to the session of the request.
