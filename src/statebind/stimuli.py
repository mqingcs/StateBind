from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from measure_twice.annotation import axis_unit, local_tick_spacing_px, target_midpoint

ScaleCondition = Literal["native", "tick_normalized"]
MarkerFamily = Literal["callout_red", "callout_cyan", "open_magenta"]


@dataclass(frozen=True)
class ViewMetadata:
    scale_condition: str
    scale_factor: float
    crop_box_source_xyxy: tuple[int, int, int, int]
    local_tick_spacing_source_px: float
    local_tick_spacing_final_px: float
    candidate_source_xy: tuple[float, float]
    candidate_final_xy: tuple[float, float]
    marker_family: str
    marker_side: int
    marker_line_width_px: int
    marker_base_width_px: float
    marker_tip_clearance_px: float
    marker_visual_tip_final_xy: tuple[float, float]
    render_padding_px: int
    output_size: tuple[int, int]


def stable_hex(*parts: object, length: int = 16) -> str:
    material = ":".join(str(part) for part in parts).encode()
    return hashlib.sha256(material).hexdigest()[:length]


def offset_sign(position: int, distance_tick: int) -> int:
    # For an even-sized pool this gives an exact 50/50 sign balance at every distance.
    return 1 if (position + distance_tick) % 2 == 0 else -1


def correct_label(round2_id: str, component: str, distance_tick: int, variant: str) -> str:
    return "A" if int(stable_hex(round2_id, component, distance_tick, variant, length=2), 16) % 2 else "B"


def candidate_source_xy(
    annotation: dict[str, Any], distance_tick: float = 0, sign: int = 1
) -> np.ndarray:
    return (
        target_midpoint(annotation)
        + axis_unit(annotation) * local_tick_spacing_px(annotation) * distance_tick * sign
    )


def _crop_box(
    image_size: tuple[int, int],
    annotation: dict[str, Any],
    scale_condition: ScaleCondition,
    required_distance_tick: float = 0,
) -> tuple[int, int, int, int]:
    width, height = image_size
    spacing = local_tick_spacing_px(annotation)
    unit = axis_unit(annotation)
    perpendicular = np.asarray([-unit[1], unit[0]])
    center = target_midpoint(annotation)
    required_along = abs(required_distance_tick) + 2.0
    if scale_condition == "tick_normalized":
        along_half = max(6.5, required_along) * spacing
        across_half = 12 * spacing
    else:
        along_half = max(max(6.5, required_along) * spacing, 80)
        across_half = max(12 * spacing, 120)
    corners = [
        center + along * unit + across * perpendicular
        for along in (-along_half, along_half)
        for across in (-across_half, across_half)
    ]
    xs = [float(point[0]) for point in corners]
    ys = [float(point[1]) for point in corners]
    left = max(0, math.floor(min(xs)))
    top = max(0, math.floor(min(ys)))
    right = min(width, math.ceil(max(xs)) + 1)
    bottom = min(height, math.ceil(max(ys)) + 1)
    if right - left < 32 or bottom - top < 32:
        raise ValueError("source crop is too small")
    return left, top, right, bottom


def _draw_marker(
    image: Image.Image,
    candidate_xy: np.ndarray,
    axis_direction: np.ndarray,
    spacing_px: float,
    marker_side: int,
    family: MarkerFamily,
) -> tuple[int, float, float, np.ndarray]:
    draw = ImageDraw.Draw(image)
    perpendicular = np.asarray([-axis_direction[1], axis_direction[0]]) * marker_side
    line_width = max(2, min(6, round(spacing_px * 0.12)))
    tip_clearance = max(4.0, spacing_px * 0.18)
    base_distance = max(7.0, spacing_px * 0.32)
    half_base = max(4.0, spacing_px * 0.19)
    shaft_distance = max(25.0, spacing_px * 1.55)
    visual_tip = candidate_xy + perpendicular * tip_clearance
    base_center = candidate_xy + perpendicular * base_distance
    shaft_start = candidate_xy + perpendicular * shaft_distance
    base_axis = axis_direction * half_base
    colors = {
        "callout_red": (232, 62, 51),
        "callout_cyan": (0, 157, 220),
        "open_magenta": (205, 68, 180),
    }
    color = colors[family]
    draw.line(
        [tuple(shaft_start), tuple(base_center)],
        fill=color,
        width=line_width,
    )
    left_base = base_center - base_axis
    right_base = base_center + base_axis
    if family == "open_magenta":
        draw.line(
            [tuple(left_base), tuple(visual_tip), tuple(right_base)],
            fill=color,
            width=line_width,
            joint="curve",
        )
    else:
        draw.polygon(
            [tuple(visual_tip), tuple(left_base), tuple(right_base)],
            fill=color,
        )
    return line_width, 2 * half_base, tip_clearance, visual_tip


def render_marked_view(
    source: Image.Image,
    annotation: dict[str, Any],
    *,
    distance_tick: float,
    sign: int,
    scale_condition: ScaleCondition,
    marker_family: MarkerFamily = "callout_red",
    normalized_tick_px: float = 28,
    crop_required_distance_tick: float | None = None,
) -> tuple[Image.Image, ViewMetadata]:
    source = source.convert("RGB")
    source_spacing = local_tick_spacing_px(annotation)
    crop_box = _crop_box(
        source.size,
        annotation,
        scale_condition,
        required_distance_tick=(
            distance_tick
            if crop_required_distance_tick is None
            else crop_required_distance_tick
        ),
    )
    cropped = source.crop(crop_box)
    scale_factor = 1.0
    if scale_condition == "tick_normalized":
        scale_factor = normalized_tick_px / source_spacing
        resized = (
            max(1, round(cropped.width * scale_factor)),
            max(1, round(cropped.height * scale_factor)),
        )
        cropped = cropped.resize(resized, Image.Resampling.LANCZOS)
    candidate_source = candidate_source_xy(annotation, distance_tick, sign)
    candidate_final = np.asarray(
        [
            (candidate_source[0] - crop_box[0]) * scale_factor,
            (candidate_source[1] - crop_box[1]) * scale_factor,
        ]
    )
    if not (
        0 <= candidate_final[0] < cropped.width
        and 0 <= candidate_final[1] < cropped.height
    ):
        raise ValueError("candidate coordinate falls outside the rendered crop")
    final_spacing = source_spacing * scale_factor
    render_padding = math.ceil(max(36.0, final_spacing * 1.9))
    padded = Image.new(
        "RGB",
        (cropped.width + 2 * render_padding, cropped.height + 2 * render_padding),
        (242, 243, 245),
    )
    padded.paste(cropped, (render_padding, render_padding))
    cropped = padded
    candidate_final += render_padding
    line_width, base_width, tip_clearance, visual_tip = _draw_marker(
        cropped,
        candidate_final,
        axis_unit(annotation),
        final_spacing,
        int(annotation["marker_side"]),
        marker_family,
    )
    metadata = ViewMetadata(
        scale_condition=scale_condition,
        scale_factor=scale_factor,
        crop_box_source_xyxy=crop_box,
        local_tick_spacing_source_px=source_spacing,
        local_tick_spacing_final_px=final_spacing,
        candidate_source_xy=(float(candidate_source[0]), float(candidate_source[1])),
        candidate_final_xy=(float(candidate_final[0]), float(candidate_final[1])),
        marker_family=marker_family,
        marker_side=int(annotation["marker_side"]),
        marker_line_width_px=line_width,
        marker_base_width_px=base_width,
        marker_tip_clearance_px=tip_clearance,
        marker_visual_tip_final_xy=(float(visual_tip[0]), float(visual_tip[1])),
        render_padding_px=render_padding,
        output_size=cropped.size,
    )
    return cropped, metadata


def _label_panel(view: Image.Image, label: str) -> Image.Image:
    header = 54
    panel = Image.new("RGB", (view.width, view.height + header), "white")
    panel.paste(view, (0, header))
    draw = ImageDraw.Draw(panel)
    font = ImageFont.load_default(size=30)
    draw.text((18, 10), label, fill=(20, 20, 20), font=font)
    return panel


def render_2afc(
    source: Image.Image,
    annotation: dict[str, Any],
    *,
    distance_tick: float,
    sign: int,
    scale_condition: ScaleCondition,
    correct_panel: Literal["A", "B"],
    marker_family: MarkerFamily = "callout_red",
) -> tuple[Image.Image, dict[str, Any]]:
    correct, correct_meta = render_marked_view(
        source,
        annotation,
        distance_tick=0,
        sign=1,
        scale_condition=scale_condition,
        marker_family=marker_family,
        crop_required_distance_tick=distance_tick,
    )
    offset, offset_meta = render_marked_view(
        source,
        annotation,
        distance_tick=distance_tick,
        sign=sign,
        scale_condition=scale_condition,
        marker_family=marker_family,
        crop_required_distance_tick=distance_tick,
    )
    if correct.size != offset.size:
        raise RuntimeError("paired views have different dimensions")
    panel_a = _label_panel(correct if correct_panel == "A" else offset, "A")
    panel_b = _label_panel(correct if correct_panel == "B" else offset, "B")
    gap = 18
    canvas = Image.new(
        "RGB",
        (panel_a.width + panel_b.width + gap, max(panel_a.height, panel_b.height)),
        (236, 238, 240),
    )
    canvas.paste(panel_a, (0, 0))
    canvas.paste(panel_b, (panel_a.width + gap, 0))
    separation = distance_tick * correct_meta.local_tick_spacing_final_px
    metadata = {
        "correct_panel": correct_panel,
        "offset_sign": sign,
        "distance_tick": distance_tick,
        "distance_pixel": separation,
        "pixel_valid": separation
        >= max(4.0, 1.25 * correct_meta.marker_base_width_px),
        "correct_view": correct_meta.__dict__,
        "offset_view": offset_meta.__dict__,
        "output_size": canvas.size,
    }
    return canvas, metadata


def render_binary(
    source: Image.Image,
    annotation: dict[str, Any],
    *,
    candidate_state: Literal["correct", "offset"],
    distance_tick: float,
    sign: int,
    marker_family: MarkerFamily = "callout_red",
) -> tuple[Image.Image, dict[str, Any]]:
    actual_distance = 0 if candidate_state == "correct" else distance_tick
    view, view_meta = render_marked_view(
        source,
        annotation,
        distance_tick=actual_distance,
        sign=sign,
        scale_condition="tick_normalized",
        marker_family=marker_family,
    )
    separation = actual_distance * view_meta.local_tick_spacing_final_px
    return view, {
        "candidate_state": candidate_state,
        "ground_truth_valid": candidate_state == "correct",
        "offset_sign": sign,
        "distance_tick": distance_tick,
        "distance_pixel": separation,
        "pixel_valid": candidate_state == "correct"
        or separation >= max(4.0, 1.25 * view_meta.marker_base_width_px),
        "view": view_meta.__dict__,
        "output_size": view.size,
    }
