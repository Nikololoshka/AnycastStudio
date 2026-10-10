# 5. SQLite until the worker reports lock contention

Date: 2026-10-10
Status: accepted

## Context

The web process and the Celery worker write to one SQLite file (WAL, PRAGMAs
in `config/settings/base.py`). The app runs locally for a few users.

## Decision

Stay on SQLite. Move to PostgreSQL when `database is locked` appears in the
worker log.

## Consequences

Code must not hold a transaction across a network call, must throttle writes
in loops, and claims work with a conditional UPDATE instead of
`SELECT ... FOR UPDATE SKIP LOCKED`.
