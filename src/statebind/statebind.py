from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from scipy.signal import find_peaks

STATEBIND_VERSION = "statebind-auto-v1"
DEFAULT_STRENGTH_WEIGHT = 0.72
MAX_EXTRAPOLATION_RATIO = 0.25


@dataclass(frozen=True)
class TickCandidate:
    position: float
    strength: float
    source: str


def _axis(
    axis_low_xy: list[float], axis_high_xy: list[float]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    origin = np.asarray(axis_low_xy, dtype=float)
    vector = np.asarray(axis_high_xy, dtype=float) - origin
    length = float(np.linalg.norm(vector))
    if not math.isfinite(length) or length < 10:
        raise ValueError("scale axis must span at least 10 pixels")
    unit = vector / length
    perpendicular = np.asarray([-unit[1], unit[0]])
    return origin, unit, perpendicular, length


def project_position(point_xy: list[float], origin: np.ndarray, unit: np.ndarray) -> float:
    return float((np.asarray(point_xy, dtype=float) - origin) @ unit)


def aggregate_numeric_anchors(
    extractions: list[dict[str, Any]],
    *,
    origin: np.ndarray,
    unit: np.ndarray,
) -> list[dict[str, Any]]:
    grouped: dict[float, list[float]] = defaultdict(list)
    confidences: dict[float, list[float]] = defaultdict(list)
    for extraction in extractions:
        if not extraction.get("include"):
            continue
        confidence = float(extraction.get("confidence", 0.0) or 0.0)
        for anchor in extraction.get("anchors", []):
            try:
                value = float(anchor["value"])
                position = project_position(anchor["tick_xy"], origin, unit)
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(value) and math.isfinite(position):
                grouped[value].append(position)
                confidences[value].append(confidence)
    aggregated = [
        {
            "value": value,
            "raw_position": float(np.median(grouped[value])),
            "position_mad": float(
                np.median(np.abs(np.asarray(grouped[value]) - np.median(grouped[value])))
            ),
            "observations": len(grouped[value]),
            "mean_extraction_confidence": float(np.mean(confidences[value])),
        }
        for value in sorted(grouped)
    ]
    repeat_supported = [anchor for anchor in aggregated if anchor["observations"] >= 2]
    return repeat_supported if len(repeat_supported) >= 2 else aggregated


def robust_position_per_value(
    anchors: list[dict[str, Any]], *, position_field: str = "raw_position"
) -> tuple[float, float] | None:
    slopes: list[float] = []
    for first in range(len(anchors)):
        for second in range(first + 1, len(anchors)):
            delta_value = float(anchors[second]["value"] - anchors[first]["value"])
            if abs(delta_value) <= 1e-12:
                continue
            slopes.append(
                float(anchors[second][position_field] - anchors[first][position_field])
                / delta_value
            )
    if not slopes:
        return None
    slope = float(np.median(slopes))
    intercept = float(
        np.median(
            [
                float(anchor[position_field]) - slope * float(anchor["value"])
                for anchor in anchors
            ]
        )
    )
    if not math.isfinite(slope) or not math.isfinite(intercept) or abs(slope) <= 1e-12:
        return None
    return slope, intercept


def _rectified_tick_profile(
    gray: np.ndarray,
    *,
    origin: np.ndarray,
    unit: np.ndarray,
    perpendicular: np.ndarray,
    length: float,
    half_width: int,
) -> tuple[np.ndarray, np.ndarray]:
    longitudinal = np.arange(0, math.ceil(length) + 1, dtype=np.float32)
    transverse = np.arange(-half_width, half_width + 1, dtype=np.float32)
    map_x = (
        origin[0]
        + longitudinal[:, None] * unit[0]
        + transverse[None, :] * perpendicular[0]
    ).astype(np.float32)
    map_y = (
        origin[1]
        + longitudinal[:, None] * unit[1]
        + transverse[None, :] * perpendicular[1]
    ).astype(np.float32)
    strip = cv2.remap(
        gray,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )
    strip = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 8)).apply(strip)
    kernel_width = max(7, 2 * (half_width // 5) + 1)
    blackhat = cv2.morphologyEx(
        strip,
        cv2.MORPH_BLACKHAT,
        cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 3)),
    )
    keep = max(3, min(12, strip.shape[1] // 5))
    strongest = np.partition(blackhat.astype(float), -keep, axis=1)[:, -keep:]
    signal = strongest.mean(axis=1)
    signal = cv2.GaussianBlur(signal[:, None], (1, 3), 0).ravel()
    return strip, signal


def detect_tick_candidates(
    image_bgr: np.ndarray,
    *,
    axis_low_xy: list[float],
    axis_high_xy: list[float],
) -> tuple[list[TickCandidate], dict[str, Any]]:
    origin, unit, perpendicular, length = _axis(axis_low_xy, axis_high_xy)
    if image_bgr.ndim == 2:
        gray = image_bgr.astype(np.uint8)
    else:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    half_width = max(18, min(70, round(length * 0.12)))
    strip, signal = _rectified_tick_profile(
        gray,
        origin=origin,
        unit=unit,
        perpendicular=perpendicular,
        length=length,
        half_width=half_width,
    )
    positive = signal[signal > 0]
    baseline = float(np.median(positive)) if len(positive) else 0.0
    spread = float(np.median(np.abs(positive - baseline))) if len(positive) else 0.0
    prominence = max(1.0, 1.5 * spread)
    peak_indices, properties = find_peaks(
        signal,
        distance=2,
        prominence=prominence,
    )
    peak_prominences = properties.get("prominences", np.zeros(len(peak_indices)))
    raw: list[tuple[float, float, str]] = [
        (float(position), float(prominence_value), "profile")
        for position, prominence_value in zip(
            peak_indices, peak_prominences, strict=True
        )
    ]

    edges = cv2.Canny(gray, 45, 140)
    minimum_line = max(5, min(18, round(length * 0.018)))
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=max(5, minimum_line),
        minLineLength=minimum_line,
        maxLineGap=3,
    )
    hough_count = 0
    if lines is not None:
        for packed in np.asarray(lines).reshape(-1, 4):
            x1, y1, x2, y2 = (float(value) for value in packed)
            vector = np.asarray([x2 - x1, y2 - y1])
            line_length = float(np.linalg.norm(vector))
            if line_length <= 0:
                continue
            alignment = abs(float(vector / line_length @ perpendicular))
            if alignment < 0.9:
                continue
            midpoint = np.asarray([(x1 + x2) / 2, (y1 + y2) / 2])
            relative = midpoint - origin
            position = float(relative @ unit)
            across = abs(float(relative @ perpendicular))
            if not -3 <= position <= length + 3 or across > half_width:
                continue
            raw.append(
                (
                    min(max(position, 0.0), length),
                    line_length * alignment**4 * (1 - 0.45 * across / half_width),
                    "hough",
                )
            )
            hough_count += 1

    if not raw:
        return [], {
            "axis_length_px": length,
            "rectified_half_width_px": half_width,
            "profile_peak_count": 0,
            "hough_segment_count": 0,
        }
    raw.sort()
    clusters: list[list[tuple[float, float, str]]] = []
    for item in raw:
        if not clusters or item[0] - np.mean([row[0] for row in clusters[-1]]) > 2.0:
            clusters.append([item])
        else:
            clusters[-1].append(item)
    combined: list[tuple[float, float, str]] = []
    for cluster in clusters:
        weights = np.asarray([max(row[1], 1e-6) for row in cluster])
        position = float(np.average([row[0] for row in cluster], weights=weights))
        score = float(max(row[1] for row in cluster) + 0.25 * np.mean(weights))
        sources = "+".join(sorted({row[2] for row in cluster}))
        combined.append((position, score, sources))
    scores = np.asarray([row[1] for row in combined])
    low, high = float(np.quantile(scores, 0.1)), float(np.quantile(scores, 0.9))
    scale = max(high - low, 1e-9)
    candidates = [
        TickCandidate(
            position=position,
            strength=float(np.clip((score - low) / scale, 0, 1)),
            source=source,
        )
        for position, score, source in combined
    ]
    return candidates, {
        "axis_length_px": length,
        "rectified_half_width_px": half_width,
        "profile_peak_count": len(peak_indices),
        "hough_segment_count": hough_count,
        "combined_candidate_count": len(candidates),
        "profile_baseline": baseline,
        "profile_mad": spread,
        "rectified_strip_shape": list(strip.shape),
    }


def snap_anchor_groups(
    anchors: list[dict[str, Any]],
    candidates: list[TickCandidate],
    *,
    strength_weight: float = 0.72,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(anchors) < 2 or not candidates:
        return [dict(anchor, snapped_position=anchor["raw_position"]) for anchor in anchors], {
            "used_cv": False,
            "reason": "insufficient anchors or tick candidates",
        }
    raw_positions = np.sort(np.asarray([anchor["raw_position"] for anchor in anchors]))
    separations = np.diff(raw_positions)
    separations = separations[separations > 2]
    if not len(separations):
        return [dict(anchor, snapped_position=anchor["raw_position"]) for anchor in anchors], {
            "used_cv": False,
            "reason": "numeric anchors do not span distinct positions",
        }
    radius = float(np.clip(0.36 * np.median(separations), 4.0, 28.0))
    snapped: list[dict[str, Any]] = []
    for anchor in anchors:
        raw_position = float(anchor["raw_position"])
        nearby = [
            candidate
            for candidate in candidates
            if abs(candidate.position - raw_position) <= radius
        ]
        if nearby:
            selected = max(
                nearby,
                key=lambda candidate: (
                    strength_weight * candidate.strength
                    - (1 - strength_weight)
                    * abs(candidate.position - raw_position)
                    / radius,
                    -abs(candidate.position - raw_position),
                ),
            )
            snapped.append(
                dict(
                    anchor,
                    snapped_position=selected.position,
                    snap_shift_px=selected.position - raw_position,
                    tick_candidate_strength=selected.strength,
                    tick_candidate_source=selected.source,
                )
            )
        else:
            snapped.append(
                dict(
                    anchor,
                    snapped_position=raw_position,
                    snap_shift_px=0.0,
                    tick_candidate_strength=0.0,
                    tick_candidate_source="raw_fallback",
                )
            )
    raw_fit = robust_position_per_value(anchors)
    snapped_fit = robust_position_per_value(snapped, position_field="snapped_position")
    if raw_fit is None or snapped_fit is None:
        return [dict(anchor, snapped_position=anchor["raw_position"]) for anchor in anchors], {
            "used_cv": False,
            "reason": "affine binding could not be fitted",
        }
    raw_sign = math.copysign(1, raw_fit[0])
    snapped_sign = math.copysign(1, snapped_fit[0])
    slope_ratio = abs(snapped_fit[0] / raw_fit[0])
    shifts = np.asarray([row["snap_shift_px"] for row in snapped], dtype=float)
    anchor_span = float(np.ptp([row["raw_position"] for row in anchors]))
    maximum_relative_anchor_mad = max(
        float(row["position_mad"]) for row in anchors
    ) / max(anchor_span, 1e-9)
    opposite_large_shifts = bool(shifts.min() < -2.0 and shifts.max() > 2.0)
    missing_tick_candidate = any(
        row["tick_candidate_source"] == "raw_fallback" for row in snapped
    )
    if raw_sign != snapped_sign or not 0.8 <= slope_ratio <= 1.25:
        return [dict(anchor, snapped_position=anchor["raw_position"]) for anchor in anchors], {
            "used_cv": False,
            "reason": "CV candidates violate anchor order or scale-span guard",
            "proposed_slope_ratio": slope_ratio,
            "snap_radius_px": radius,
        }
    if maximum_relative_anchor_mad > 0.25:
        return [dict(anchor, snapped_position=anchor["raw_position"]) for anchor in anchors], {
            "used_cv": False,
            "reason": "repeat anchor coordinates are not stable enough for CV snapping",
            "maximum_relative_anchor_mad": maximum_relative_anchor_mad,
            "snap_radius_px": radius,
        }
    if missing_tick_candidate:
        return [dict(anchor, snapped_position=anchor["raw_position"]) for anchor in anchors], {
            "used_cv": False,
            "reason": (
                "detected graduation support is incomplete"
            ),
            "opposite_large_shifts": opposite_large_shifts,
            "missing_tick_candidate": missing_tick_candidate,
            "snap_radius_px": radius,
        }
    return snapped, {
        "used_cv": any(abs(row["snap_shift_px"]) > 1e-6 for row in snapped),
        "reason": "accepted",
        "snap_radius_px": radius,
        "slope_ratio": slope_ratio,
        "median_absolute_snap_shift_px": float(
            np.median([abs(row["snap_shift_px"]) for row in snapped])
        ),
        "mean_selected_tick_strength": float(
            np.mean([row["tick_candidate_strength"] for row in snapped])
        ),
    }


def fit_state_binding(
    image_bgr: np.ndarray,
    *,
    axis_low_xy: list[float],
    axis_high_xy: list[float],
    extractions: list[dict[str, Any]],
    strength_weight: float = DEFAULT_STRENGTH_WEIGHT,
) -> dict[str, Any] | None:
    origin, unit, perpendicular, length = _axis(axis_low_xy, axis_high_xy)
    anchors = aggregate_numeric_anchors(extractions, origin=origin, unit=unit)
    raw_fit = robust_position_per_value(anchors)
    if raw_fit is None:
        return None
    candidates, detector = detect_tick_candidates(
        image_bgr,
        axis_low_xy=axis_low_xy,
        axis_high_xy=axis_high_xy,
    )
    snapped, snap = snap_anchor_groups(
        anchors,
        candidates,
        strength_weight=strength_weight,
    )
    cv_fit = robust_position_per_value(snapped, position_field="snapped_position")
    if cv_fit is None:
        cv_fit = raw_fit
    return {
        "axis_origin_xy": origin.tolist(),
        "axis_unit_xy": unit.tolist(),
        "axis_perpendicular_xy": perpendicular.tolist(),
        "axis_length_px": length,
        "anchors": snapped,
        "raw_position_per_value": raw_fit[0],
        "raw_position_intercept": raw_fit[1],
        "cv_position_per_value": cv_fit[0],
        "cv_position_intercept": cv_fit[1],
        "tick_candidates": [candidate.__dict__ for candidate in candidates],
        "tick_detector": detector,
        "snap_diagnostics": snap,
    }


def value_to_coordinate(
    binding: dict[str, Any], value: float, *, method: str = "cv"
) -> np.ndarray:
    if method not in {"raw", "cv", "auto"}:
        raise ValueError("method must be raw, cv, or auto")
    if method == "auto":
        values = np.asarray([row["value"] for row in binding["anchors"]], dtype=float)
        span = float(np.ptp(values))
        outside = max(float(values.min() - value), float(value - values.max()), 0.0)
        extrapolation_ratio = outside / span if span > 1e-12 else float("inf")
        method = (
            "cv"
            if binding["snap_diagnostics"].get("used_cv")
            and extrapolation_ratio <= MAX_EXTRAPOLATION_RATIO
            else "raw"
        )
    slope = float(binding[f"{method}_position_per_value"])
    intercept = float(binding[f"{method}_position_intercept"])
    position = slope * float(value) + intercept
    return np.asarray(binding["axis_origin_xy"], dtype=float) + np.asarray(
        binding["axis_unit_xy"], dtype=float
    ) * position
