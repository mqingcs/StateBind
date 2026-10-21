#!/usr/bin/env python3
"""Rebuild the central StateBind counts and accuracies from compact records."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RECORDS = ROOT / "records"
OUTPUT = ROOT / "reproduced"
PROVIDERS = ("doubao", "gemini", "qwen_batch_no_thinking")
INTERFACES = ("numeric", "calibrated_numeric", "oracle_physicalized")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def image_balanced_effect(
    rows: list[dict[str, Any]], provider: str, left: str, right: str
) -> float:
    lookup = {
        (row["interface"], row["real200_id"], row["distance_from_interval_tick"], row["order_condition"]): bool(row["correct"])
        for row in rows
        if row["provider"] == provider
    }
    by_image: dict[str, list[float]] = defaultdict(list)
    for key, left_correct in lookup.items():
        interface, image_id, distance, order = key
        if interface != left:
            continue
        right_correct = lookup[(right, image_id, distance, order)]
        by_image[image_id].append(float(right_correct) - float(left_correct))
    return mean(mean(values) for values in by_image.values())


def majority_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["request_id"]].append(row)
    by_interface: dict[str, list[bool]] = defaultdict(list)
    by_image_delta: dict[str, list[float]] = defaultdict(list)
    correctness: dict[tuple[str, str, int, str], bool] = {}
    for request_id, group in grouped.items():
        if len(group) != 3:
            raise RuntimeError(f"expected three providers for {request_id}")
        choices = Counter(row["choice"] for row in group)
        choice = choices.most_common(1)[0][0]
        correct = choice == group[0]["correct_panel"]
        interface = group[0]["interface"]
        by_interface[interface].append(correct)
        correctness[
            (
                interface,
                group[0]["real200_id"],
                int(group[0]["distance_from_interval_tick"]),
                group[0]["order_condition"],
            )
        ] = correct
    for (interface, image_id, distance, order), numeric_correct in correctness.items():
        if interface != "numeric":
            continue
        physicalized = correctness[("oracle_physicalized", image_id, distance, order)]
        by_image_delta[image_id].append(float(physicalized) - float(numeric_correct))
    return {
        "accuracy": {
            interface: mean(values) for interface, values in sorted(by_interface.items())
        },
        "physicalized_minus_numeric_image_balanced": mean(
            mean(values) for values in by_image_delta.values()
        ),
    }


def main() -> None:
    calls = load_jsonl(RECORDS / "formal_calls6696.jsonl")
    cells = load_jsonl(DATA / "manifests/cells744.jsonl")
    pairs = load_jsonl(DATA / "manifests/pairs372.jsonl")
    route = load_jsonl(DATA / "manifests/route_cells72.jsonl")
    annotations = load_jsonl(DATA / "annotations/statebind200_geometry.jsonl")
    if (len(calls), len(cells), len(pairs), len(route), len(annotations)) != (
        6696,
        744,
        372,
        72,
        200,
    ):
        raise RuntimeError("artifact cardinalities do not match the paper protocol")

    provider_results: dict[str, Any] = {}
    for provider in PROVIDERS:
        provider_rows = [row for row in calls if row["provider"] == provider]
        provider_results[provider] = {
            "calls": len(provider_rows),
            "interfaces": {
                interface: {
                    "calls": len(selected := [row for row in provider_rows if row["interface"] == interface]),
                    "correct": sum(bool(row["correct"]) for row in selected),
                    "accuracy": mean(bool(row["correct"]) for row in selected),
                }
                for interface in INTERFACES
            },
            "physicalized_minus_numeric_image_balanced": image_balanced_effect(
                calls, provider, "numeric", "oracle_physicalized"
            ),
        }
    route_correct = sum(bool(row["route_correct"]) for row in route)
    summary = {
        "schema_version": "statebind-artifact-rebuilt-core-v1",
        "dataset": {
            "images": len(annotations),
            "pairs": len(pairs),
            "ordered_cells": len(cells),
            "formal_calls": len(calls),
        },
        "providers": provider_results,
        "majority": majority_summary(calls),
        "factorial_route": {
            "cells": len(route),
            "images": len({row["real200_id"] for row in route}),
            "correct": route_correct,
            "precision": route_correct / len(route),
        },
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "rebuilt_core_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
