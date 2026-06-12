# Changelog

## 2026-05-31

- Added persistent task job queue recovery, health checks, SQLite WAL/busy-timeout setup, and safer upload transaction cleanup.
- Improved task polling UX for detail pages and running lists, including local retirement of completed running rows and clearer failed-task recovery actions.
- Strengthened upload validation on both client and server, including field-level errors, preserved form state, and per-file preview status.
- Added report helpers for multi-spec artifact isolation, HTML report cache freshness checks, and PDF cache reuse.
- Limited history rendering to the most recent 100 tasks to avoid unbounded list pages.
- Deferred page scripts and added frontend/API/storage/report/queue regression tests.
- Documented local service, verification, UI/API contracts, schema version, queue state machine, and report cache behavior.
