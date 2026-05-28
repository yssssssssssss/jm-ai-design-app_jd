from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SPEC_ID = "jm-ai"
B_DESIGN_SPEC_ID = "b-design"
BOTTOM_NAV_SPEC_ID = "bottom-nav"


@dataclass(frozen=True)
class AuditSpec:
    id: str
    label: str
    spec_path: Path
    asset_index_path: Path


AUDIT_SPECS = {
    DEFAULT_SPEC_ID: AuditSpec(
        id=DEFAULT_SPEC_ID,
        label="JM AI 设计规范",
        spec_path=ROOT_DIR / "references" / "jm-ai-design-spec.md",
        asset_index_path=ROOT_DIR / "references" / "spec-assets.json",
    ),
    B_DESIGN_SPEC_ID: AuditSpec(
        id=B_DESIGN_SPEC_ID,
        label="京东 B 端设计规范（B-design Agent 组件规范）",
        spec_path=ROOT_DIR / "references" / "specs" / "b-design.md",
        asset_index_path=ROOT_DIR / "references" / "spec-assets-b-design.json",
    ),
    BOTTOM_NAV_SPEC_ID: AuditSpec(
        id=BOTTOM_NAV_SPEC_ID,
        label="导航类-底部导航栏规范",
        spec_path=ROOT_DIR / "references" / "specs" / "bottom-nav.md",
        asset_index_path=ROOT_DIR / "references" / "spec-assets-bottom-nav.json",
    ),
}


def list_audit_specs() -> list[AuditSpec]:
    return list(AUDIT_SPECS.values())


def get_audit_spec(spec_id: str | None) -> AuditSpec:
    spec_ids = audit_spec_ids_from_value(spec_id)
    return AUDIT_SPECS.get(spec_ids[0], AUDIT_SPECS[DEFAULT_SPEC_ID])


def get_audit_specs(spec_ids: str | list[str] | tuple[str, ...] | None) -> list[AuditSpec]:
    valid_spec_ids = [
        spec_id for spec_id in audit_spec_ids_from_value(spec_ids) if spec_id in AUDIT_SPECS
    ]
    return [AUDIT_SPECS[spec_id] for spec_id in valid_spec_ids] or [
        AUDIT_SPECS[DEFAULT_SPEC_ID]
    ]


def audit_spec_ids_from_value(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return [DEFAULT_SPEC_ID]
    raw_values = [value] if isinstance(value, str) else list(value)
    spec_ids: list[str] = []
    for raw in raw_values:
        for part in str(raw or "").split(","):
            spec_id = part.strip()
            if spec_id and spec_id not in spec_ids:
                spec_ids.append(spec_id)
    return spec_ids or [DEFAULT_SPEC_ID]


def serialize_audit_spec_ids(spec_ids: list[str] | tuple[str, ...]) -> str:
    return ",".join(validate_audit_spec_ids(list(spec_ids)))


def validate_audit_spec_id(spec_id: str | None) -> str:
    return validate_audit_spec_ids(spec_id)[0]


def validate_audit_spec_ids(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    spec_ids = audit_spec_ids_from_value(value)
    if any(spec_id not in AUDIT_SPECS for spec_id in spec_ids):
        raise ValueError("unknown audit spec")
    return spec_ids
