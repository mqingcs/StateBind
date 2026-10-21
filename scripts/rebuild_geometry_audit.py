#!/usr/bin/env python3
"""Rebuild the anonymized 40-image geometry audit and sensitivity result."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("doubao", "gemini", "qwen_batch_no_thinking")
POINT_FIELDS = ("axis_start_xy", "axis_end_xy", "low_value_tick_xy", "high_value_tick_xy")
POINT_LIST_FIELDS = ("target_state_interval_xy", "local_tick_centers_xy")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def point(value: Any) -> list[float]:
    return [float(value[0]), float(value[1])]


def subtract(left: list[float], right: list[float]) -> list[float]:
    return [left[0] - right[0], left[1] - right[1]]


def dot(left: list[float], right: list[float]) -> float:
    return left[0] * right[0] + left[1] * right[1]


def unit(value: list[float]) -> list[float]:
    length = math.hypot(value[0], value[1])
    if length < 1e-9:
        raise RuntimeError("degenerate geometry direction")
    return [value[0] / length, value[1] / length]


def value_direction(geometry: dict[str, Any]) -> list[float]:
    if geometry.get("low_value_tick_xy") is not None and geometry.get("high_value_tick_xy") is not None:
        return unit(
            subtract(
                point(geometry["high_value_tick_xy"]),
                point(geometry["low_value_tick_xy"]),
            )
        )
    return unit(subtract(point(geometry["axis_end_xy"]), point(geometry["axis_start_xy"])))


def tick_spacing(geometry: dict[str, Any]) -> float:
    direction = unit(
        subtract(point(geometry["axis_end_xy"]), point(geometry["axis_start_xy"]))
    )
    ticks = geometry.get("local_tick_centers_xy") or [
        geometry["low_value_tick_xy"],
        geometry["high_value_tick_xy"],
    ]
    positions = sorted(dot(point(value), direction) for value in ticks)
    gaps = [b - a for a, b in zip(positions, positions[1:]) if b - a > 0.5]
    if not gaps:
        raise RuntimeError("tick centers do not span distinct positions")
    return median(gaps)


def aligned_direction(left: list[float], right: list[float]) -> tuple[list[float], float]:
    cosine = max(-1.0, min(1.0, dot(left, right)))
    if cosine < 0:
        right = [-right[0], -right[1]]
        cosine = -cosine
    combined = [left[0] + right[0], left[1] + right[1]]
    return unit(combined), math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def target_difference(
    left: dict[str, Any], right: dict[str, Any], span: bool
) -> tuple[float, float, float]:
    direction, angle = aligned_direction(value_direction(left), value_direction(right))
    mean_spacing = (tick_spacing(left) + tick_spacing(right)) / 2
    left_values = sorted(
        dot(point(value), direction) for value in left["target_state_interval_xy"]
    )
    right_values = sorted(
        dot(point(value), direction) for value in right["target_state_interval_xy"]
    )
    if span:
        if len(left_values) != len(right_values):
            raise RuntimeError("paired span annotations have different endpoint counts")
        differences = [
            abs(a - b) / mean_spacing
            for a, b in zip(left_values, right_values)
        ]
        target = mean(differences)
    else:
        target = abs(mean(left_values) - mean(right_values)) / mean_spacing
    ratio = max(tick_spacing(left), tick_spacing(right)) / min(
        tick_spacing(left), tick_spacing(right)
    )
    return target, angle, ratio


def reader_effect(
    calls: list[dict[str, Any]],
    *,
    provider: str | None,
    excluded: set[str],
) -> float:
    by_cell: dict[tuple[str, str, int, str], Any] = {}
    for row in calls:
        if row["real200_id"] in excluded:
            continue
        key = (
            row["interface"],
            row["real200_id"],
            int(row["distance_from_interval_tick"]),
            row["order_condition"],
        )
        if provider is None:
            by_cell.setdefault(key, {})[row["provider"]] = bool(row["correct"])
        elif row["provider"] == provider:
            by_cell[key] = bool(row["correct"])
    numeric = {(key[1], key[2], key[3]) for key in by_cell if key[0] == "numeric"}
    physical = {
        (key[1], key[2], key[3])
        for key in by_cell
        if key[0] == "oracle_physicalized"
    }
    by_image: dict[str, list[float]] = defaultdict(list)
    for identifier, distance, order in numeric & physical:
        before = by_cell[("numeric", identifier, distance, order)]
        after = by_cell[("oracle_physicalized", identifier, distance, order)]
        if provider is None:
            before = sum(before.values()) >= 2
            after = sum(after.values()) >= 2
        by_image[identifier].append(float(after) - float(before))
    return mean(mean(values) for values in by_image.values())


def quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def geometry_points(geometry: dict[str, Any]) -> list[list[float]]:
    points = [point(geometry[field]) for field in POINT_FIELDS if geometry.get(field) is not None]
    for field in POINT_LIST_FIELDS:
        points.extend(point(value) for value in geometry.get(field) or [])
    return points


def coordinate_integrity(
    primary: dict[str, dict[str, Any]],
    second: dict[str, dict[str, Any]],
    source: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    checked = {"primary": 0, "second": 0}
    out_of_bounds: list[dict[str, Any]] = []
    for label, rows in (("primary", primary), ("second", second)):
        for identifier in sorted(second):
            width = float(source[identifier]["image_width"])
            height = float(source[identifier]["image_height"])
            for value in geometry_points(rows[identifier]):
                checked[label] += 1
                if not (0 <= value[0] <= width and 0 <= value[1] <= height):
                    out_of_bounds.append(
                        {"benchmark_id": identifier, "source": label, "xy": value}
                    )
    second_frames = {row.get("coordinate_frame") for row in second.values()}
    if second_frames != {"original_image_pixels"}:
        raise RuntimeError(f"unexpected second-review coordinate frames: {second_frames}")
    return {
        "final_xy_frame": "displayed_image_pixels",
        "primary_points_checked": checked["primary"],
        "second_reviewer_points_checked": checked["second"],
        "out_of_bounds_points": len(out_of_bounds),
        "stored_image_pixel_frame_shared": True,
        "normalized_1000_rescaled_again": False,
        "second_reviewer_coordinate_frame": "original_image_pixels",
    }


def main() -> None:
    primary = {
        row["benchmark_id"]: row["geometry"]
        for row in load_jsonl(ROOT / "data/annotations/statebind200_geometry.jsonl")
    }
    second = {
        row["benchmark_id"]: row["geometry"]
        for row in load_jsonl(ROOT / "data/annotations/second_geometry40.jsonl")
    }
    manifest = {
        row["benchmark_id"]: row
        for row in load_jsonl(ROOT / "data/manifests/geometry_audit40.jsonl")
    }
    source = {
        row["benchmark_id"]: row
        for row in load_jsonl(ROOT / "data/source_index200.jsonl")
    }
    selection = json.loads(
        (ROOT / "data/manifests/geometry_audit40_selection.json").read_text()
    )
    if len(primary) != 200 or len(second) != 40 or set(second) != set(manifest):
        raise RuntimeError("geometry audit manifests are incomplete")
    if set(second) - set(source) or selection["sample_size"] != 40:
        raise RuntimeError("geometry audit source index or selection summary is incomplete")

    targets: list[float] = []
    angles: list[float] = []
    spacing_ratios: list[float] = []
    per_item = []
    for identifier in sorted(second):
        target, angle, ratio = target_difference(
            primary[identifier],
            second[identifier],
            manifest[identifier]["operator_stratum"] == "span_difference",
        )
        targets.append(target)
        angles.append(angle)
        spacing_ratios.append(ratio)
        per_item.append(
            {
                "benchmark_id": identifier,
                "target_difference_ticks": target,
                "local_scale_orientation_difference_degrees": angle,
                "tick_spacing_ratio": ratio,
            }
        )

    disagreements = {
        row["benchmark_id"] for row in per_item if row["target_difference_ticks"] > 1
    }
    calls = [
        row
        for row in load_jsonl(ROOT / "records/formal_calls6696.jsonl")
        if row["interface"] in {"numeric", "oracle_physicalized"}
    ]
    result = {
        "images": 40,
        "families": len({row["instrument_family"] for row in manifest.values()}),
        "pre_outcome_selection": selection,
        "coordinate_integrity": coordinate_integrity(primary, second, source),
        "all_second_review_images_included": all(
            row.get("include") is True for row in second.values()
        ),
        "target_difference_ticks": {
            "median": median(targets),
            "p90": quantile(targets, 0.90),
            "within_half_tick": sum(value <= 0.5 for value in targets),
            "within_one_tick": sum(value <= 1.0 for value in targets),
        },
        "local_scale_orientation_difference_degrees_median": median(angles),
        "tick_spacing_ratio_median": median(spacing_ratios),
        "greater_than_one_tick_images": sorted(disagreements),
        "majority_effect": {
            "complete": reader_effect(calls, provider=None, excluded=set()),
            "excluding_greater_than_one_tick": reader_effect(
                calls, provider=None, excluded=disagreements
            ),
        },
        "single_reader_effect_excluding_greater_than_one_tick": {
            provider: reader_effect(calls, provider=provider, excluded=disagreements)
            for provider in PROVIDERS
        },
    }
    expected_path = (
        ROOT
        / "round3/generated/statebind_second_annotator40/paper_analysis/analysis_summary.json"
    )
    if expected_path.exists():
        expected = json.loads(expected_path.read_text())
        checks = {
            "target median": (
                result["target_difference_ticks"]["median"],
                expected["independent_geometry"]["target_difference_ticks"]["median"],
            ),
            "majority full": (
                result["majority_effect"]["complete"],
                expected["main_effect_sensitivity"]["readers"]["majority"]["full_effect"],
            ),
            "majority sensitivity": (
                result["majority_effect"]["excluding_greater_than_one_tick"],
                expected["main_effect_sensitivity"]["readers"]["majority"][
                    "excluding_gt1_tick_effect"
                ],
            ),
            "primary coordinate points": (
                result["coordinate_integrity"]["primary_points_checked"],
                expected["coordinate_integrity"]["primary_points_checked"],
            ),
            "second-review coordinate points": (
                result["coordinate_integrity"]["second_reviewer_points_checked"],
                expected["coordinate_integrity"]["secondary_points_checked"],
            ),
        }
        for label, (actual, reference) in checks.items():
            if not math.isclose(actual, reference, rel_tol=0, abs_tol=1e-12):
                raise RuntimeError(f"{label} does not match paper-facing summary")
    output = ROOT / "reproduced/rebuilt_geometry_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
