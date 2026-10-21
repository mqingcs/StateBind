from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np


def point(value: Any, field: str) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        raise ValueError(f"{field} must be an [x, y] point")
    result = [float(value[0]), float(value[1])]
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{field} contains a non-finite coordinate")
    return result


def validate_annotation(
    payload: dict[str, Any],
    *,
    expected_round2_id: str,
    expected_image_sha256: str,
    image_size: tuple[int, int],
) -> dict[str, Any]:
    if payload.get("round2_id") != expected_round2_id:
        raise ValueError("round2_id does not match the selected task")
    if payload.get("image_sha256") != expected_image_sha256:
        raise ValueError("image_sha256 does not match the frozen image")
    include = bool(payload.get("include"))
    clean: dict[str, Any] = {
        "round2_id": expected_round2_id,
        "image_sha256": expected_image_sha256,
        "image_width": int(image_size[0]),
        "image_height": int(image_size[1]),
        "include": include,
        "visibility": str(payload.get("visibility", "")),
        "occlusion": str(payload.get("occlusion", "")),
        "unique_state": bool(payload.get("unique_state")),
        "annotator_confidence": int(payload.get("annotator_confidence", 0)),
        "exclusion_reason": str(payload.get("exclusion_reason", "")).strip(),
        "notes": str(payload.get("notes", "")).strip(),
        "scale_branch": str(payload.get("scale_branch", "")).strip(),
        "target_rule": str(payload.get("target_rule", "")).strip(),
        "marker_side": int(payload.get("marker_side", 0)),
    }
    if clean["visibility"] not in {"clear", "usable", "unclear"}:
        raise ValueError("visibility must be clear, usable, or unclear")
    if clean["occlusion"] not in {"none", "partial", "severe"}:
        raise ValueError("occlusion must be none, partial, or severe")
    if not 1 <= clean["annotator_confidence"] <= 5:
        raise ValueError("annotator_confidence must be between 1 and 5")
    if not include:
        if not clean["exclusion_reason"]:
            raise ValueError("excluded tasks require an exclusion_reason")
        clean.update(
            {
                "axis_start_xy": None,
                "axis_end_xy": None,
                "local_tick_centers_xy": [],
                "target_state_interval_xy": [],
                "minor_tick_value": None,
                "marker_side": None,
                "target_value_interval": None,
            }
        )
        return clean

    if not clean["unique_state"]:
        raise ValueError("include=false is required when the physical state is not unique")
    if not clean["scale_branch"]:
        raise ValueError("scale_branch is required")
    if not clean["target_rule"]:
        raise ValueError("target_rule is required")
    if clean["marker_side"] not in {-1, 1}:
        raise ValueError("marker_side must be -1 or 1")
    start = point(payload.get("axis_start_xy"), "axis_start_xy")
    end = point(payload.get("axis_end_xy"), "axis_end_xy")
    if math.dist(start, end) < 10:
        raise ValueError("axis anchors must be at least 10 pixels apart")
    ticks_raw = payload.get("local_tick_centers_xy", [])
    if not isinstance(ticks_raw, list) or len(ticks_raw) < 3:
        raise ValueError("at least three local tick centers are required")
    ticks = [point(item, "local_tick_centers_xy") for item in ticks_raw]
    target_raw = payload.get("target_state_interval_xy", [])
    if not isinstance(target_raw, list) or len(target_raw) != 2:
        raise ValueError("target_state_interval_xy requires exactly two boundary clicks")
    target = [point(item, "target_state_interval_xy") for item in target_raw]
    minor_tick_value = float(payload.get("minor_tick_value", 0))
    if not math.isfinite(minor_tick_value) or minor_tick_value <= 0:
        raise ValueError("minor_tick_value must be a positive finite number")
    target_value_lower = float(payload.get("target_value_lower"))
    target_value_upper = float(payload.get("target_value_upper"))
    if not all(math.isfinite(value) for value in (target_value_lower, target_value_upper)):
        raise ValueError("target value interval must be finite")
    if target_value_lower > target_value_upper:
        raise ValueError("target_value_lower cannot exceed target_value_upper")
    width, height = image_size
    for field, points in {
        "axis": [start, end],
        "ticks": ticks,
        "target": target,
    }.items():
        if any(not (0 <= x < width and 0 <= y < height) for x, y in points):
            raise ValueError(f"{field} contains a point outside the source image")
    clean.update(
        {
            "axis_start_xy": start,
            "axis_end_xy": end,
            "local_tick_centers_xy": ticks,
            "target_state_interval_xy": target,
            "minor_tick_value": minor_tick_value,
            "target_value_interval": [target_value_lower, target_value_upper],
            "exclusion_reason": "",
        }
    )
    spacing = local_tick_spacing_px(clean)
    if spacing < 1:
        raise ValueError("adjacent local tick spacing is below one pixel")
    return clean


def axis_unit(annotation: dict[str, Any]) -> np.ndarray:
    start = np.asarray(annotation["axis_start_xy"], dtype=float)
    end = np.asarray(annotation["axis_end_xy"], dtype=float)
    vector = end - start
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        raise ValueError("axis has zero length")
    return vector / norm


def local_tick_spacing_px(annotation: dict[str, Any]) -> float:
    unit = axis_unit(annotation)
    ticks = np.asarray(annotation["local_tick_centers_xy"], dtype=float)
    projected = np.sort(ticks @ unit)
    differences = np.diff(projected)
    differences = differences[differences > 0.5]
    if not len(differences):
        raise ValueError("tick centers do not span distinct positions along the axis")
    return float(np.median(differences))


def target_midpoint(annotation: dict[str, Any]) -> np.ndarray:
    target = np.asarray(annotation["target_state_interval_xy"], dtype=float)
    return target.mean(axis=0)


def target_uncertainty_ticks(annotation: dict[str, Any]) -> float:
    unit = axis_unit(annotation)
    target = np.asarray(annotation["target_state_interval_xy"], dtype=float)
    width_px = abs(float((target[1] - target[0]) @ unit))
    return width_px / local_tick_spacing_px(annotation)


def annotation_pair_metrics(
    left: dict[str, Any], right: dict[str, Any]
) -> dict[str, float]:
    left_unit = axis_unit(left)
    right_unit = axis_unit(right)
    if float(left_unit @ right_unit) < 0:
        right_unit = -right_unit
    mean_unit = left_unit + right_unit
    mean_unit /= np.linalg.norm(mean_unit)
    spacing_left = local_tick_spacing_px(left)
    spacing_right = local_tick_spacing_px(right)
    mean_spacing = (spacing_left + spacing_right) / 2
    midpoint_difference = target_midpoint(left) - target_midpoint(right)
    agreement_ticks = abs(float(midpoint_difference @ mean_unit)) / mean_spacing
    cosine = float(np.clip(left_unit @ right_unit, -1, 1))
    left_value = np.asarray(left["target_value_interval"], dtype=float).mean()
    right_value = np.asarray(right["target_value_interval"], dtype=float).mean()
    mean_minor_tick = (
        float(left["minor_tick_value"]) + float(right["minor_tick_value"])
    ) / 2
    return {
        "target_difference_ticks": agreement_ticks,
        "axis_angle_degrees": math.degrees(math.acos(cosine)),
        "tick_spacing_left_px": spacing_left,
        "tick_spacing_right_px": spacing_right,
        "tick_spacing_ratio": max(spacing_left, spacing_right)
        / min(spacing_left, spacing_right),
        "target_uncertainty_left_ticks": target_uncertainty_ticks(left),
        "target_uncertainty_right_ticks": target_uncertainty_ticks(right),
        "numeric_target_difference_ticks": abs(left_value - right_value) / mean_minor_tick,
        "numeric_uncertainty_left_ticks": (
            float(left["target_value_interval"][1])
            - float(left["target_value_interval"][0])
        )
        / float(left["minor_tick_value"]),
        "numeric_uncertainty_right_ticks": (
            float(right["target_value_interval"][1])
            - float(right["target_value_interval"][0])
        )
        / float(right["minor_tick_value"]),
    }
