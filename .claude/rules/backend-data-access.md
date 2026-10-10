---
paths:
  - "backend/**/views/**"
  - "backend/**/repositories/**"
  - "backend/**/models.py"
  - "backend/common/access/**"
  - "backend/services/usecases/**"
---

# Backend data access

- Filter by `request.user` inside the queryset, not with a check afterwards.
- Never accept a user id from the client.
- Someone else's row answers 404, not 403: a 403 confirms the row exists.
- Reach `PublicationTarget` only through its publication's owner.
- Never keep a transaction open across a network call: web and worker write
  to the same SQLite file and the other side gets `database is locked`.
- Throttle writes in loops; upload progress is stored on whole percents only.
- SQLite has no `SELECT ... FOR UPDATE SKIP LOCKED`; claim with a conditional
  UPDATE and decide by rowcount.
