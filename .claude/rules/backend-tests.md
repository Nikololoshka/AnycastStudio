---
paths:
  - "backend/**/tests/**"
---

# Backend tests

- New behaviour needs a test, written as Given / When / Then.
- Always cover: who sees what, tokens, upload offsets, every way a platform
  can fail.
- Use cases and platforms: `IsolatedAsyncioTestCase` against the in-memory
  fakes in `services/tests/fakes/` and `platforms/tests/fakes/`.
- Adapters, views, end to end: Django `TestCase`; the network is
  `platforms/tests/fakes/http.py::FakeSession` injected into
  `services.wiring.Container.open_session`; YouTube uses the `httplib2`-like
  double behind `YouTubeApi.videos`.
- Test settings have no network, no Redis, no disk; don't add a test that
  needs them.
