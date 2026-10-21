#!/usr/bin/env python3
"""Verify the StateBind open-source release without model calls."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "data/source_index200.jsonl": 200,
    "data/annotations/statebind200_geometry.jsonl": 200,
    "data/annotations/second_geometry40.jsonl": 40,
    "data/manifests/geometry_audit40.jsonl": 40,
    "data/manifests/pairs372.jsonl": 372,
    "data/manifests/cells744.jsonl": 744,
    "data/manifests/requests2232.jsonl": 2232,
    "data/manifests/route_cells72.jsonl": 72,
    "records/formal_calls6696.jsonl": 6696,
    "records/factorial_cells744.jsonl": 744,
    "records/proposals/doubao200.jsonl": 200,
    "records/proposals/gemini200.jsonl": 200,
    "records/validators/qwen_on_gemini191.jsonl": 191,
    "records/validators/qwen_on_doubao184.jsonl": 184,
}
REQUIRED_JSON = {
    "data/manifests/geometry_audit40_selection.json",
    "data/manifests/route_images36.json",
    "protocol/model_protocol.json",
    "artifact_build_summary.json",
}
SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"sk-(?:ws-)?[0-9A-Za-z._-]{20,}"),
]
FORBIDDEN_TEXT = (
    "/Users/",
    "/home/",
    "C:\\Users\\",
    "credential_alias",
    "provider_request_id",
)
FORBIDDEN_PARTS = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "venv",
}
FORBIDDEN_FILES = {".DS_Store", ".env"}
TEXT_SUFFIXES = {
    ".bib",
    ".cls",
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sty",
    ".tex",
    ".txt",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    counts: dict[str, int] = {}
    for relative, expected in REQUIRED.items():
        path = ROOT / relative
        if not path.exists():
            raise RuntimeError(f"missing {relative}")
        rows = load_jsonl(path)
        counts[relative] = len(rows)
        if len(rows) != expected:
            raise RuntimeError(f"{relative}: expected {expected}, got {len(rows)}")
    for relative in REQUIRED_JSON:
        path = ROOT / relative
        if not path.exists():
            raise RuntimeError(f"missing {relative}")
        json.loads(path.read_text())

    calls = load_jsonl(ROOT / "records/formal_calls6696.jsonl")
    keys = [(row["provider"], row["request_id"]) for row in calls]
    if len(set(keys)) != len(keys):
        raise RuntimeError("formal call composite keys are not unique")
    matrix = Counter((row["provider"], row["interface"]) for row in calls)
    if set(matrix.values()) != {744} or len(matrix) != 9:
        raise RuntimeError(f"formal call matrix is incomplete: {matrix}")

    source = load_jsonl(ROOT / "data/source_index200.jsonl")
    if len({row["benchmark_id"] for row in source}) != 200:
        raise RuntimeError("source index benchmark IDs are not unique")
    primary_ids = {
        row["benchmark_id"]
        for row in load_jsonl(ROOT / "data/annotations/statebind200_geometry.jsonl")
    }
    second = load_jsonl(ROOT / "data/annotations/second_geometry40.jsonl")
    if len({row["benchmark_id"] for row in second}) != 40:
        raise RuntimeError("second geometry benchmark IDs are not unique")
    if not {row["benchmark_id"] for row in second}.issubset(primary_ids):
        raise RuntimeError("second geometry audit is not a subset of StateBind-200")
    cells = load_jsonl(ROOT / "data/manifests/cells744.jsonl")
    if len({row["cell_id"] for row in cells}) != 744:
        raise RuntimeError("cell IDs are not unique")
    route = load_jsonl(ROOT / "data/manifests/route_cells72.jsonl")
    if len({row["cell_id"] for row in route}) != 72:
        raise RuntimeError("route cell IDs are not unique")
    selection = json.loads(
        (ROOT / "data/manifests/geometry_audit40_selection.json").read_text()
    )
    if selection["sample_size"] != 40 or selection["seed"] != 20260822:
        raise RuntimeError("geometry-audit selection summary changed")
    if any(selection["browser_blinding"].values()):
        raise RuntimeError("geometry-audit browser blinding is incomplete")

    scanned_files = 0
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if ".git" in relative.parts:
            continue
        if any(part in FORBIDDEN_PARTS for part in relative.parts):
            raise RuntimeError(f"forbidden cache or workspace directory: {relative}")
        if path.is_file() and (
            path.name in FORBIDDEN_FILES
            or path.name.startswith(".env.")
            or path.suffix.lower() in {".pyc", ".pyo", ".swp", ".tmp"}
            or path.name.endswith("~")
        ):
            raise RuntimeError(f"forbidden temporary or sensitive file: {relative}")
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(errors="ignore")
        scanned_files += 1
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            raise RuntimeError(f"credential-like string in {path.relative_to(ROOT)}")
        if any(value.lower() in text.lower() for value in FORBIDDEN_TEXT):
            raise RuntimeError(f"private path or provider credential metadata in {path.relative_to(ROOT)}")

    result = {
        "schema_version": "statebind-artifact-verification-v1",
        "required_counts": counts,
        "formal_matrix_cells": dict(sorted((f"{p}/{i}", n) for (p, i), n in matrix.items())),
        "unique_call_keys": len(set(keys)),
        "unique_cell_ids": len({row["cell_id"] for row in cells}),
        "unique_route_cell_ids": len({row["cell_id"] for row in route}),
        "text_files_scanned": scanned_files,
        "credential_scan": "clean",
        "private_path_scan": "clean",
        "workspace_cache_scan": "clean",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
