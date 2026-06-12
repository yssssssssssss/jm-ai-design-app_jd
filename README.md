# JM AI Design Web App

Single-port FastAPI app for JM AI design-spec screenshot audits.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env` and edit the values. The app loads `.env` from the project root. Real environment variables still override values from `.env`.

```bash
cp .env.example .env
```

Key fields:

- `AUDIT_MODEL_PROVIDER`: audit provider, either `openai` or `jdcloud`. Defaults to `openai`.
- `OPENAI_API_KEY`: LLM API key.
- `OPENAI_BASE_URL`: OpenAI-compatible endpoint, for example `https://api.openai.com/v1` or your gateway `/v1` URL.
- `OPENAI_AUDIT_MODEL`: vision-capable model used for design audits.
- `OPENAI_REASONING_EFFORT`: optional reasoning effort, for example `xhigh` when the provider supports it.
- `OPENAI_TIMEOUT_SECONDS`: model request timeout in seconds. Defaults to `180`.
- `JDCLOUD_OPENAI_API_KEY`, `JDCLOUD_OPENAI_BASE_URL`, `JDCLOUD_OPENAI_AUDIT_MODEL`: required when `AUDIT_MODEL_PROVIDER=jdcloud`. JDCloud audits use Chat Completions.
- `JDCLOUD_OPENAI_REASONING_EFFORT`, `JDCLOUD_OPENAI_TIMEOUT_SECONDS`: optional JDCloud-specific reasoning and timeout settings.
- `APP_SECRET_KEY`: long random string for session signing.
- `REGISTER_INVITE_CODE`: invite code required for self-registration.
- `DATA_DIR`: SQLite, uploads, artifacts, and reports directory.

Do not commit `.env`.

## Run

Use one worker in phase 1. The task runner is in-process, so multiple web workers would need an external queue.

This project is not a separate frontend/backend dev-server setup. HTML pages, static assets, and API routes are served by the same FastAPI process. The fixed local frontend and backend port is `8011`.

For local development on this machine:

```bash
npm start
npm stop
npm restart
npm run status
npm run health
npm run logs
```

The fixed local URL is `http://127.0.0.1:8011/`.

```bash
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
```

Open `http://localhost:8000`.

## Accounts

Users self-register with `REGISTER_INVITE_CODE` and become normal users automatically. Admin users can see all tasks and reports. Normal users can only see their own tasks, reports, and artifacts.

The initial admin account is created from `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD` when no active admin exists.

## Test

```bash
file .venv/bin/python
.venv/bin/python -m pytest -q
```

For the local pre-handoff check, run:

```bash
npm run verify
```

`npm run verify` checks the Python runtime architecture, validates `app/static/app.js`, compiles `app/`, runs the full pytest suite, and runs `git diff --check`.

On Apple Silicon, do not claim full pytest passed unless `.venv/bin/python` is native `arm64`.

## Runtime Contracts

- `/healthz` returns database schema, worker state, and queue job counts.
- SQLite runs with WAL mode and a busy timeout; interrupted queued/running jobs are recovered on startup.
- `审核规范` is a checkbox multi-select. Nothing is selected by default, and submitting without a selected spec is rejected.
- Multi-spec audits store comma-separated ids in `tasks.audit_spec_id` and render isolated per-spec report sections.
- Task detail pages poll `/tasks/{id}/status`; running task lists poll `/tasks/running/status`.
- Failed task detail responses include failure actions for returning to the upload flow.
- HTML reports are reused when audit artifacts have not changed; PDF reports are reused when the renderer version and report freshness match.
- History renders the most recent 100 tasks to avoid unbounded list pages.

## Storage

SQLite lives at `data/app.db`. Uploaded originals and generated reports live under `data/uploads/<task_id>/`.

Back up both `data/app.db` and `data/uploads`.
