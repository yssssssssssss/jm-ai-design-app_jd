# Size Experiment Design

## Purpose

The project already lets users provide a manuscript size for uploaded UI images. Today that size is used as model context and in the final report, but the image is not resampled and the measurement tool is not given the declared design size during normal task execution.

This design adds an offline experiment flow to compare whether size-aware processing improves three target areas:

- spacing, padding, and component-size judgments
- typography, line-height, and density judgments
- overall layout and module understanding

The experiment does not claim accuracy without human review. It produces structured differences across variants so the team can inspect historical manuscripts before changing the production audit path.

## Scope

Build a sidecar experiment tool, not a production mode.

The first version should not:

- change the normal upload or task flow
- change database schema
- make normalized images the default audit input
- create an automatic accuracy score
- add an annotation or human-review system

The tool can be run against either a historical task image or a standalone image path.

Example commands:

```bash
.venv/bin/python scripts/run_size_experiment.py --task-id 123 --design-size 1440x900
.venv/bin/python scripts/run_size_experiment.py --image data/uploads/123/originals/image-001.png --design-size 1440x900
```

## Variants

### Baseline

The baseline variant mirrors the current behavior:

- send the original image to the model
- include actual image size and declared manuscript size in the prompt
- run measurement without `--design-size`

This gives a stable comparison point against the existing implementation.

### Scaled Metrics

The scaled-metrics variant keeps the original image unchanged and makes geometry conversion explicit.

The prompt should include:

- actual image size
- declared manuscript size
- `scale_x = actual_width / declared_width`
- `scale_y = actual_height / declared_height`
- whether the scale is approximately uniform

The model must still return bbox coordinates in original image pixels. Spacing, component-size, typography, and density reasoning should refer to design pixels after scale conversion.

The measurement tool should run with:

```bash
measure_regions.py image.png regions.json --design-size WIDTHxHEIGHT
```

This makes `bbox_design_px`, converted spacing, and nearest token comparisons available as evidence.

### Normalized Preview

The normalized-preview variant keeps the original image as the coordinate and evidence source, and adds a second image that is scaled to the declared width.

Normalized preview size:

```text
normalized_width = declared_width
normalized_height = round(actual_height * declared_width / actual_width)
```

The preview should not be stretched to the declared height. If the normalized height differs meaningfully from the declared height, the experiment report should flag the declared size as potentially mismatched with the image aspect ratio.

The model receives both images:

- original image: source of truth for bbox, small details, colors, and screenshot annotations
- normalized preview: auxiliary context for layout density and module understanding

The prompt must require:

- all bbox values use original image pixel coordinates
- normalized preview is only auxiliary context
- color and fine-line judgments prefer the original image
- if original and preview lead to conflicting conclusions, prefer the original and record the uncertainty in `cannot_verify`

## Output Layout

Each experiment run writes a timestamped run directory under `data/experiments`.

Suggested layout:

```text
data/experiments/<run_id>/<image_key>/
  original.png
  baseline/
    audit.json
    regions.json
    measurements.json
  scaled-metrics/
    audit.json
    regions.json
    measurements.json
  normalized-preview/
    normalized.png
    audit.json
    regions.json
    measurements.json
  comparison.json
  comparison.html
```

Failures are recorded per variant. One failed variant should not prevent comparison output for the successful variants.

## Comparison JSON

`comparison.json` should be machine-readable and stable enough for later aggregation.

Minimum structure:

```json
{
  "image": "data/uploads/123/originals/image-001.png",
  "actual_size": [2880, 1800],
  "declared_size": [1440, 900],
  "scale": {
    "x": 2.0,
    "y": 2.0,
    "uniform": true
  },
  "variants": {
    "baseline": {
      "status": "succeeded",
      "audit_path": "baseline/audit.json",
      "measurements_path": "baseline/measurements.json"
    },
    "scaled_metrics": {
      "status": "succeeded",
      "audit_path": "scaled-metrics/audit.json",
      "measurements_path": "scaled-metrics/measurements.json"
    },
    "normalized_preview": {
      "status": "succeeded",
      "audit_path": "normalized-preview/audit.json",
      "measurements_path": "normalized-preview/measurements.json",
      "normalized_path": "normalized-preview/normalized.png"
    }
  },
  "diff": {
    "issue_count_by_category": {},
    "new_issues": [],
    "removed_issues": [],
    "changed_severity": [],
    "changed_confidence": [],
    "cannot_verify_count": {},
    "bbox_coverage": {},
    "layout_context": {}
  }
}
```

The first version should keep diff matching simple and explainable. Match issues by a normalized key from `category`, `location`, and `current_observation`. This will not be perfect, but it is easier to debug than a hidden semantic matcher.

## Comparison HTML

`comparison.html` is for human inspection. It should not declare a winner.

It should show:

- original image metadata and declared design size
- scale values and uniformity warning
- the three overall conclusions side by side
- `screen_context` differences
- counts for target categories: spacing/layout/component size, typography/density, and layout/module understanding
- new, removed, and changed issues
- `cannot_verify` counts and item differences
- bbox coverage and number of measurable regions
- converted measurement evidence for scaled-metrics
- normalized preview image when generated

All model-generated text must be HTML-escaped.

## Error Handling

The tool should be useful even when model calls or evidence tools fail.

Per variant, record:

- `status`: `succeeded` or `failed`
- `error_message`: concise failure text
- paths that were produced before failure

The comparison output should still be written if at least one variant succeeds.

Invalid or missing design size should fail fast with a clear message. A declared size must be positive integers in `WIDTHxHEIGHT` form.

If `scale_x` and `scale_y` differ meaningfully, the report should keep running but mark geometric conclusions as lower-confidence evidence.

## Implementation Boundaries

Add small reusable helpers only where they remove duplication:

- parse design size
- compute scale metadata
- create normalized preview
- run a variant and capture errors
- build comparison data
- render comparison HTML

Do not add a framework or task subsystem. A single script plus a small helper module is enough for the first version.

Potential file layout:

```text
scripts/run_size_experiment.py
app/size_experiment.py
tests/test_size_experiment.py
```

`app/size_experiment.py` can hold deterministic helpers and comparison logic. The script should remain a thin CLI wrapper.

## Test Plan

Tests should cover deterministic behavior, not whether the model is correct.

Required tests:

- parse `1440x900`
- reject malformed or non-positive design sizes
- compute scale metadata for uniform and non-uniform cases
- normalize preview dimensions without stretching to declared height
- flag aspect-ratio mismatch when normalized height differs from declared height
- pass `--design-size` to measurement execution for scaled-metrics
- produce stable output layout
- produce comparison output when one variant fails
- handle empty `issues`, null bbox, empty `regions`, and missing `cannot_verify`
- escape HTML in model-generated fields

Model calls should be mocked in tests.

## Acceptance Criteria

- A historical task or standalone image can be run through all three variants.
- Output is written under `data/experiments/<run_id>/`.
- `comparison.json` contains actual size, declared size, scale metadata, variant statuses, and diff sections.
- `comparison.html` opens locally and shows the three variants side by side.
- Scaled-metrics measurements include design-pixel conversions.
- Normalized-preview uses an auxiliary image without changing the original-image bbox contract.
- A failed variant does not erase successful variant outputs.
- Normal production audits behave exactly as before.
