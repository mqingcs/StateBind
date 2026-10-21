#!/usr/bin/env python3
"""Rebuild the frozen Factorial StateBind route from per-cell recombinations."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
METHODS = ("DD", "DG", "GD", "GG")
PROVIDERS = ("doubao", "gemini", "qwen_batch_no_thinking")
FOUR = "4/4 invariant"
THREE = "3/4 invariant"
TARGET = "target-source sensitive"
LATTICE = "lattice-source sensitive"
INTERACTION = "checkerboard/interaction"
INVALID = "invalid/component-insufficient"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def candidate_choice(value: float, candidate_a: float, candidate_b: float) -> str | None:
    a_distance = abs(value - candidate_a)
    b_distance = abs(value - candidate_b)
    if a_distance < b_distance:
        return "A"
    if b_distance < a_distance:
        return "B"
    return None


def classify(choices: dict[str, str | None], valid: dict[str, bool]) -> tuple[str, str | None]:
    usable = {
        method: choices[method]
        for method in METHODS
        if valid[method] and choices[method] in {"A", "B"}
    }
    counts = Counter(usable.values())
    if len(usable) < 3:
        return INVALID, None
    majority = counts.most_common(1)[0][0]
    if len(usable) == 3:
        return (THREE, majority) if len(counts) == 1 else (INVALID, None)
    if len(counts) == 1:
        return FOUR, majority
    if counts[majority] == 3:
        return THREE, majority
    if usable["DD"] == usable["DG"] and usable["GD"] == usable["GG"]:
        return TARGET, None
    if usable["DD"] == usable["GD"] and usable["DG"] == usable["GG"]:
        return LATTICE, None
    if usable["DD"] == usable["GG"] and usable["DG"] == usable["GD"]:
        return INTERACTION, None
    return INVALID, None


def main() -> None:
    rows = load_jsonl(ROOT / "records/factorial_cells744.jsonl")
    released_route = {
        row["cell_id"]: row
        for row in load_jsonl(ROOT / "data/manifests/route_cells72.jsonl")
    }
    if len(rows) != 744 or len(released_route) != 72:
        raise RuntimeError("factorial evidence is incomplete")

    rebuilt_route: dict[str, dict[str, Any]] = {}
    category_counts: Counter[str] = Counter()
    policy_correctness = {provider: [] for provider in PROVIDERS}
    transitions = {provider: Counter() for provider in PROVIDERS}
    for row in rows:
        choices = {
            method: (
                candidate_choice(
                    float(row["factorial_values"][method]),
                    float(row["candidate_a_value"]),
                    float(row["candidate_b_value"]),
                )
                if row["factorial_values"][method] is not None
                else None
            )
            for method in METHODS
        }
        if choices != row["factorial_choices"]:
            raise RuntimeError(f"candidate mapping changed for {row['real200_id']}")
        category, category_choice = classify(choices, row["factorial_component_valid"])
        if category != row["factorial_category"] or category_choice != row["category_choice"]:
            raise RuntimeError(f"factorial classification changed for {row['real200_id']}")
        category_counts[category] += 1

        route = (
            int(row["distance_from_interval_tick"]) >= 4
            and category == FOUR
            and category_choice in {"A", "B"}
        )
        if route != bool(row["route"]):
            raise RuntimeError(f"route predicate changed for {row['real200_id']}")
        route_correct = category_choice == row["correct_panel"] if route else None
        if route_correct != row["route_correct"]:
            raise RuntimeError(f"route scoring changed for {row['real200_id']}")

        cell_id = (
            f"{row['real200_id']}__d{row['distance_from_interval_tick']}__"
            f"{row['order_condition']}"
        )
        if route:
            rebuilt_route[cell_id] = row
        for provider in PROVIDERS:
            before = bool(row["numeric_correctness"][provider])
            after = bool(route_correct) if route else before
            policy_correctness[provider].append(after)
            transitions[provider][
                f"{'correct' if before else 'wrong'}_to_"
                f"{'correct' if after else 'wrong'}"
            ] += 1

    if set(rebuilt_route) != set(released_route):
        raise RuntimeError("rebuilt and released route cell IDs differ")
    route_correct_count = sum(bool(row["route_correct"]) for row in rebuilt_route.values())
    result = {
        "schema_version": "statebind-artifact-rebuilt-factorial-v1",
        "cells": len(rows),
        "category_counts": dict(sorted(category_counts.items())),
        "selected_rule": {
            "rule_name": "four_only",
            "minimum_distance": 4,
            "test_labels_used_for_selection": False,
        },
        "route": {
            "cells": len(rebuilt_route),
            "images": len({row["real200_id"] for row in rebuilt_route.values()}),
            "correct": route_correct_count,
            "candidate_precision": route_correct_count / len(rebuilt_route),
            "cell_coverage": len(rebuilt_route) / len(rows),
        },
        "fallback_policy": {
            provider: {
                "accuracy": mean(policy_correctness[provider]),
                "transitions": dict(sorted(transitions[provider].items())),
            }
            for provider in PROVIDERS
        },
    }
    output = ROOT / "reproduced/rebuilt_factorial_summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
