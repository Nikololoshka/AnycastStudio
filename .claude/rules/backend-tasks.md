---
paths:
  - "backend/services/**"
  - "backend/**/repositories/**"
---

# Backend background tasks

- All Celery tasks live in `services/tasks.py`, named `<area>.<task>`.
- A task is idempotent and claims its work first, as
  `DjangoTargetRepository.claim_queued_target` does: `acks_late` + claim gives
  effectively-once.
- No task-level retry: the pipeline decides what happens on failure.
- Never retry what the platform decided (rejected file, exhausted quota):
  every attempt burns YouTube quota.
- Uploads don't resume; `StaleTargetSweeper` fails abandoned targets. Only
  `PublicationTarget.confirmation_state` survives between tasks.
