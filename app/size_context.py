from __future__ import annotations

from typing import Any


DesignSize = tuple[int, int]


def compute_scale(actual_size: DesignSize, declared_size: DesignSize) -> dict[str, Any]:
    actual_width, actual_height = actual_size
    declared_width, declared_height = declared_size
    scale_x = actual_width / declared_width
    scale_y = actual_height / declared_height
    uniform = abs(scale_x - scale_y) <= 0.02
    return {
        "x": round(scale_x, 4),
        "y": round(scale_y, 4),
        "uniform": uniform,
        "aspect_ratio_mismatch": not uniform,
    }
