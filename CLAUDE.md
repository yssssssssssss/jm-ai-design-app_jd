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

## Local Service

- The app is a single-port FastAPI service: frontend pages, static assets, and backend API routes all run on `http://127.0.0.1:8011/`.
- Local tmux session name: `jm-ai-design-8011`.
