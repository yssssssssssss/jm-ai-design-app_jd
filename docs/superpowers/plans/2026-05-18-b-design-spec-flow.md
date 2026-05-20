# B-design Spec Flow Integration TODO

> **For future Codex work:** use this file as the progress tracker for the B-design spec integration. Update checkboxes as work is completed. Do not expand scope into URL, H5, or web-page capture work.

**Goal:** Make the already-ingested B-design specification assets fully usable in the existing screenshot audit product flow.

**Current status:** B-design reference material has been ingested as local assets. The product flow still needs code changes and verification so a user-selected spec controls database records, prompts, audit execution, report rendering, and asset references.

**Done means:** A B-design task can be created from the product UI, persists `audit_spec_id=b-design`, runs the audit against B-design spec text rather than JM AI fixed text, renders B-design reference assets in the report, and passes automated plus manual end-to-end checks.

---

## Progress

- [x] B-design PDF source files are present under `references/B-design/`.
- [x] B-design spec text is generated at `references/specs/b-design.md`.
- [x] B-design asset index is generated at `references/spec-assets-b-design.json`.
- [x] B-design snippet images are generated under `assets/spec-snippets/b-design/`.
- [x] B-design is registered in `app/spec_registry.py`.
- [x] Database migration is fixed and verified from schema version 3 to 4.
- [x] Task creation stores the selected `audit_spec_id`.
- [x] Task detail/report pages display the selected audit spec correctly.
- [x] Audit execution reads the selected spec's `spec_path`.
- [x] Prompt text is parameterized by spec instead of hard-coding JM AI wording everywhere.
- [x] Report rendering loads the selected spec's `asset_index_path`.
- [x] PDF export preserves selected spec assets.
- [x] Automated tests cover the critical spec-selection path.
- [ ] Manual end-to-end B-design task succeeds and produces a B-design-focused report.

---

## Task 1: Verify Asset Inventory

**Purpose:** Treat the ingested B-design materials as a stable product asset set before wiring runtime behavior to them.

**Files:**
- `references/B-design/`
- `references/specs/b-design.md`
- `references/spec-assets-b-design.json`
- `assets/spec-snippets/b-design/`
- `scripts/ingest_b_design_spec.py`

**Checklist:**
- [x] Confirm expected PDF count under `references/B-design/` (11 PDFs).
- [x] Confirm generated PNG count under `assets/spec-snippets/b-design/` (81 PNGs).
- [x] Confirm `references/spec-assets-b-design.json` parses as JSON.
- [x] Confirm every asset URL in `references/spec-assets-b-design.json` has a matching local PNG.
- [x] Confirm `references/specs/b-design.md` references only existing snippet URLs.

**Suggested verification:**

```bash
find references/B-design -type f -name '*.pdf' | wc -l
find assets/spec-snippets/b-design -type f -name '*.png' | wc -l
node -e "const fs=require('fs'); const j=JSON.parse(fs.readFileSync('references/spec-assets-b-design.json','utf8')); console.log(j.spec_id, j.assets.length)"
```

---

## Task 2: Fix Database Migration

**Purpose:** Existing installations must upgrade safely so product flow can persist the selected audit spec.

**Files:**
- `app/db.py`
- `app/models.py`
- `app/repositories.py`
- tests for database migration/repository behavior

**Checklist:**
- [x] Add or fix migration path from schema version 3 to version 4.
- [x] Ensure existing `tasks` tables get `audit_spec_id text not null default 'jm-ai'`.
- [x] Ensure newly created databases include `audit_spec_id`.
- [x] Ensure old tasks read as `audit_spec_id='jm-ai'`.
- [x] Add regression test for a version 3 database migrating to version 4.
- [x] Verify local `data/app.db` can be migrated without losing tasks.

**Known current blocker:**

`data/app.db` reports `pragma user_version = 3`, and `tasks` currently lacks `audit_spec_id`. Product flow cannot be considered connected until this is fixed.

---

## Task 3: Complete Task Creation Flow

**Purpose:** The selected spec must become part of the task record, not just a UI field.

**Files:**
- `app/templates/upload.html`
- `app/routes/tasks.py`
- `app/repositories.py`
- `app/spec_registry.py`
- route/repository tests

**Checklist:**
- [x] Confirm upload form posts `audit_spec_id`.
- [x] Validate `audit_spec_id` against `app/spec_registry.py`.
- [x] Persist selected spec through `create_task()`.
- [x] Preserve `jm-ai` as the default when no spec is posted.
- [x] Show a clear error for unknown spec ids.
- [x] Add tests for valid B-design selection and invalid spec rejection.

---

## Task 4: Complete Task Detail and Report Metadata

**Purpose:** Users and reports must clearly show which spec was used.

**Files:**
- `app/routes/tasks.py`
- `app/templates/task_detail.html`
- `app/report_renderer.py`
- report rendering tests

**Checklist:**
- [x] Task detail page shows the selected audit spec label.
- [x] HTML report metadata includes the selected audit spec label.
- [x] Existing JM AI reports continue to render.
- [x] Old tasks without explicit spec behave as JM AI tasks.
- [x] Tests cover report/task rendering for both JM AI and B-design.

---

## Task 5: Wire Selected Spec Into Audit Execution

**Purpose:** This is the core product-flow connection. A B-design task must audit against B-design spec text.

**Files:**
- `app/task_runner.py`
- `app/spec_registry.py`
- `app/openai_audit.py`
- `app/prompt_builder.py`
- task runner tests

**Checklist:**
- [x] Replace fixed `SPEC_PATH` usage with lookup by `task.audit_spec_id`.
- [x] Pass selected spec text into the default auditor.
- [x] Keep injected test auditors backward-compatible.
- [x] Ensure dual-audit mode uses the selected spec text.
- [x] Add tests proving B-design task reads `references/specs/b-design.md`.
- [x] Add tests proving JM AI task still reads `references/jm-ai-design-spec.md`.

**Known current blocker:**

`app/task_runner.py` still has fixed `SPEC_PATH = references/jm-ai-design-spec.md` behavior. Until this changes, B-design selection is not truly connected to model audit behavior.

---

## Task 6: Parameterize Prompt Wording

**Purpose:** Avoid contaminating B-design audits with JM AI-specific rules and labels.

**Files:**
- `app/prompt_builder.py`
- `app/openai_audit.py`
- prompt tests

**Checklist:**
- [x] Introduce spec metadata such as spec id, label, and focus areas.
- [x] Replace generic assistant identity text that hard-codes JM AI.
- [x] Keep JM AI-specific color/button/tag focus only for JM AI spec.
- [x] Add B-design-specific focus for Agent components, task planning, task nodes, status bars, and generating cards.
- [x] Parameterize fallback recommendation text.
- [x] Add tests that B-design prompts do not contain JM AI fixed audit focus.
- [x] Add tests that JM AI prompts remain compatible with existing behavior.

---

## Task 7: Wire Selected Spec Assets Into Reports

**Purpose:** Reports should cite and display the reference assets belonging to the selected spec.

**Files:**
- `app/routes/tasks.py`
- `app/report_renderer.py`
- `app/pdf_renderer.py`
- artifact access tests
- report renderer tests

**Checklist:**
- [x] Use selected spec's `asset_index_path` when rendering current reports.
- [x] Ensure `/spec-snippets/b-design/...` assets are served by static routing.
- [x] Ensure B-design reports show B-design snippets.
- [x] Ensure JM AI reports show JM AI snippets.
- [x] Verify PDF export includes selected spec assets.
- [x] Add tests for asset URL access and report output.

---

## Task 8: Automated Verification

**Purpose:** Lock the integration so future edits do not quietly fall back to JM AI.

**2026-05-18 note:** Direct Python verification passed for B-design prompt focus, B-design parse fallback wording, B-design report asset selection, PDF local URL rewriting, default auditor spec-text selection, task detail label, valid B-design task creation, and unknown spec rejection. `pytest` commands are currently stuck in uninterruptible process state (`UEs`) in the local environment and do not return output even after `kill -9`; rerun them after clearing those processes or restarting the machine.

**Checklist:**
- [ ] Run targeted database migration tests.
- [ ] Run targeted route/repository tests.
- [ ] Run targeted prompt tests.
- [ ] Run targeted task runner tests.
- [ ] Run targeted report renderer tests.
- [ ] Run full relevant pytest selection.

**Suggested command:**

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest \
  tests/test_artifact_access.py \
  tests/test_openai_audit.py \
  tests/test_report_renderer.py \
  tests/test_task_runner.py \
  -q
```

Add any new test files to this command when they are created.

---

## Task 9: Manual End-to-End Verification

**Purpose:** Prove the product flow works as a user would experience it.

**Checklist:**
- [ ] Start the local FastAPI app.
- [ ] Log in through the browser.
- [ ] Create a new task with audit spec `B-design Agent 组件规范`.
- [ ] Upload a screenshot containing an Agent component.
- [ ] Confirm task status becomes `succeeded`.
- [ ] Confirm database row stores `audit_spec_id='b-design'`.
- [ ] Confirm report language focuses on B-design Agent component rules.
- [ ] Confirm report references `/spec-snippets/b-design/...` assets.
- [ ] Confirm PDF download works if PDF export is part of the current flow.

---

## Notes For Future Work

- Keep this effort scoped to B-design spec integration in the existing screenshot audit flow.
- Do not add URL, H5, web-page, or app-link capture features under this plan.
- Prefer small changes that preserve old JM AI task behavior.
- Treat database migration and `task_runner` spec selection as the two hard blockers.
