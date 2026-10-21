#!/usr/bin/env python3
"""Run the compact artifact's offline record-level checks."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run_json(script: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def close(actual: float, expected: float) -> None:
    if not math.isclose(actual, expected, rel_tol=0, abs_tol=5e-6):
        raise RuntimeError(f"expected {expected}, got {actual}")


def main() -> None:
    verified = run_json("verify_artifact.py")
    core = run_json("rebuild_core_results.py")
    factorial = run_json("rebuild_factorial_results.py")
    geometry = run_json("rebuild_geometry_audit.py")

    dataset = core["dataset"]
    majority = core["majority"]
    route = factorial["route"]
    numeric = majority["accuracy"]["numeric"]
    physicalized = majority["accuracy"]["oracle_physicalized"]
    gain = majority["physicalized_minus_numeric_image_balanced"]
    redraw = geometry["target_difference_ticks"]
    sensitivity = geometry["majority_effect"]["excluding_greater_than_one_tick"]

    if dataset != {
        "formal_calls": 6696,
        "images": 200,
        "ordered_cells": 744,
        "pairs": 372,
    }:
        raise RuntimeError(f"unexpected dataset cardinalities: {dataset}")
    close(numeric, 0.7553763440860215)
    close(physicalized, 0.9112903225806451)
    close(gain, 0.15299479166666666)
    close(redraw["median"], 0.07991382277103434)
    if redraw["within_half_tick"] != 37 or redraw["within_one_tick"] != 38:
        raise RuntimeError(f"unexpected redraw agreement counts: {redraw}")
    close(sensitivity, 0.1554232804232804)
    if (
        route["cells"] != 72
        or route["correct"] != 66
        or route["images"] != 36
        or not math.isclose(route["candidate_precision"], 66 / 72)
    ):
        raise RuntimeError(f"unexpected route summary: {route}")
    integrity = geometry["coordinate_integrity"]
    if integrity["out_of_bounds_points"] != 0:
        raise RuntimeError(f"coordinate bounds check failed: {integrity}")

    print(
        "StateBind-200: 200 annotated images; Paired128: 128 images, "
        "372 pairs, 744 ordered cells per interface/model, 6,696 formal calls"
    )
    print(
        f"Majority: Numeric {100 * numeric:.2f}% -> Physicalized "
        f"{100 * physicalized:.2f}% ({100 * gain:+.2f} pp)"
    )
    print(
        "Independent redraw: median "
        f"{redraw['median']:.2f} tick; {redraw['within_half_tick']}/40 within "
        f"0.5 tick; {redraw['within_one_tick']}/40 within 1 tick"
    )
    print(
        "Sensitivity excluding the two >1-tick redraws: "
        f"{100 * sensitivity:+.2f} pp"
    )
    print(
        f"Selective route: {route['correct']}/{route['cells']} correct "
        f"({100 * route['candidate_precision']:.2f}%) across {route['images']} images"
    )
    print(
        "Coordinate audit: "
        f"{integrity['primary_points_checked']} primary + "
        f"{integrity['second_reviewer_points_checked']} second-review points, "
        "all in bounds"
    )
    print(
        "Artifact checks: "
        f"{verified['text_files_scanned']} text files scanned; credentials and "
        "private paths clean"
    )
    print("PASS")


if __name__ == "__main__":
    main()
