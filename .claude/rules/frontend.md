---
paths:
  - "frontend/src/**"
---

# Frontend

The SPA renders, collects input and shows progress; business logic is on the
server.

- Server state belongs to an RTK Query endpoint in `src/api/`. Slices hold
  client state only: editor draft, current upload, theme, language.
- Components call RTK Query hooks, never `fetch`; the only exception is
  `services/upload/chunkedUpload.ts`.
- Build from HeroUI 3 components before writing your own markup; don't add a
  second component library.
- Style with Tailwind utilities in `className`; no inline `style`, CSS modules
  or per-component CSS.
- Brand logos only via `components/PlatformGlyph`; other icons from
  `lucide-react`.
- Animate with `motion`, under `MotionConfig reducedMotion="user"`.
- Colors, spacing and fonts come from the tokens in `src/styles.css`. Never
  hardcode hex; add a token for both light and dark themes.
- Every user-visible string goes through `useTranslation` and
  `src/locales/<lang>/*.json`; keep `en` and `ru` in sync, keys are typed from
  `en`.
- Tests (Vitest) only for pure functions such as hashtag normalization and
  chunk arithmetic; no component tests.
