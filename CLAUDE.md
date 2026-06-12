# Project Notes for Agents

## Runtime and Tests

- This repo has previously had `pytest` hang in macOS `UEs` state when run with the existing `.venv`, because `.venv/bin/python` points to an x86_64 Miniconda Python on an arm64 Mac.
- Before running tests on Apple Silicon, check:
  `file .venv/bin/python`
- Prefer a native arm64 Python environment, for example `/opt/homebrew/bin/python3.11`, or rebuild `.venv` as arm64.
- If a `pytest` process enters `UEs`, do not keep spawning more test runs. `kill -9` may not clear it; restart Codex App or reboot macOS.
- Do not claim full `pytest` has passed unless the command completed successfully in a non-Rosetta/native environment.

## Audit Spec Isolation

- Audit spec ids:
  - `jm-ai`: JM AI 设计规范
  - `b-design`: 京东 B 端设计规范（B-design Agent 组件规范）
- Multiple selected specs are stored as a comma-separated string in `tasks.audit_spec_id`, for example `jm-ai,b-design`.
- Multi-spec audits must run independently per spec and render separate report sections.
- B-design audits must not use JM AI prompt metadata, `jm-audit-*` identifiers, JM AI token rules, or JM AI spec text.
- B-design audits must use the routed flow: first identify whether the screenshot matches components covered by `references/B-design/`, then audit only with `通用审核原则` plus the matched component sections from `references/specs/b-design.md`.
- If no B-design Agent component is matched, report the B-design audit as not applicable / not covered and do not output generic B-side UI risk findings.
- JM AI token/color rules apply only when the selected spec label is exactly `JM AI 设计规范`.

## UI Contract

- `审核规范` uses checkbox multi-select, not a dropdown.
- No audit spec should be selected by default.
- Submitting without any selected spec must be rejected.
- Upload validation errors re-render the upload page with field-level errors and preserve title, selected specs, and hidden screen-size values.
- Upload file previews show file name, size, and validation status.
- Task detail pages expose `#task-status`, `#task-summary`, `#task-error`, `#task-failure-actions`, `#task-report-links`, and per-image `data-image-id` update targets.
- `/tasks/{task_id}/status` returns raw status, Chinese status label, back link, summary/error, optional report links, failure actions, and image statuses.
- `/tasks/running/status` returns only visible active tasks (`queued` and `running`); completed rows should retire locally before disappearing.
- History pages intentionally render only the most recent 100 tasks.

## Local Service

- The app is a single-port FastAPI service: frontend pages, static assets, and backend API routes all run on `http://127.0.0.1:8011/`.
- Local tmux session name: `jm-ai-design-8011`.
- `npm run verify` runs the local handoff gate: Python architecture check, JS syntax check, app compile, full pytest, and `git diff --check`.

## Storage and Reports

- SQLite schema version is `5`.
- New databases are created by `init_db`; existing unversioned core schemas are rejected rather than guessed.
- Task jobs are stored in `task_jobs` with `queued`, `running`, `succeeded`, and `failed` states.
- Startup recovery requeues interrupted `queued`/`running` jobs and normalizes interrupted running tasks.
- HTML reports may be served from cache when report artifacts are older than `report.html`.
- PDF reports may be served from cache when `report.pdf.version` matches the current renderer and the PDF is newer than the HTML report.
