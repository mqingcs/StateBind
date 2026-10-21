from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

# This module independently implements the public FlagEvalMM MeasureBench evaluator
# semantics at vendor/FlagEvalMM commit fef27ec696c532d12f0db389bcbbf79eab0e4c41.

NUMBER_RE = re.compile(
    r"(?P<fraction>[+\-−]?\d+\s*/\s*[+\-−]?\d+)"
    r"|(?P<decimal>[+\-−]?(?:\d*\.\d+|\d+\.\d*))"
    r"|(?P<integer>[+\-−]?\d+)"
)
TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")


@dataclass(frozen=True)
class ParsedAnswer:
    value: float | None
    unit: str


@dataclass(frozen=True)
class Score:
    value: bool
    unit: bool | None
    number_error_rate: float | None = None

    @property
    def full(self) -> bool:
        return self.value and (self.unit is None or self.unit)


def normalize_string(text: str) -> str:
    replacements = {"′": "'", " ": " ", "‐": "-", "−": "-", "–": "-", "⋅": "·"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def extract_answer(text: str) -> str:
    for indicator in ["Answer:", "Answer", "答案：", "答案:", "答案"]:
        if indicator in text:
            return text.split(indicator)[-1].strip()
    boxed = re.search(r"\\boxed\{([^}]+)\}", text)
    return boxed.group(1).strip() if boxed else text


def extract_numbers(text: str) -> list[float]:
    """Match the official evaluator: fractions and decimals, in textual order."""
    values: list[float] = []
    for match in NUMBER_RE.finditer(text):
        token = match.group(0).replace("−", "-").strip()
        try:
            if match.lastgroup == "fraction":
                numerator, denominator = re.split(r"\s*/\s*", token, maxsplit=1)
                if int(denominator) != 0:
                    values.append(int(numerator) / int(denominator))
            else:
                values.append(float(token))
        except ValueError:
            continue
    return values


def parse_answer(text: str) -> ParsedAnswer:
    """Convenience view of the official rightmost-number answer convention."""
    stripped = normalize_string(extract_answer(text.strip()))
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and data.get("value") is not None:
        try:
            return ParsedAnswer(float(data["value"]), str(data.get("unit") or "").strip())
        except (TypeError, ValueError):
            pass
    numbers = extract_numbers(stripped)
    if not numbers:
        return ParsedAnswer(None, "")
    # Unit is only diagnostic here. Official unit scoring searches the full response.
    last_match = list(NUMBER_RE.finditer(stripped))[-1]
    return ParsedAnswer(numbers[-1], stripped[last_match.end() :].strip(" \t\n:;,.()[]{}"))


def _time_to_seconds(parts: list[str] | tuple[str, ...]) -> int:
    return sum(scale * int(part) for scale, part in zip([3600, 60, 1], parts) if part != "")


def _normalize_unit_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text.lower()).replace("µ", "μ")


def _coerce_numeric_string_interval(interval: list[Any]) -> list[Any]:
    """Repair numeric labels serialized as strings without changing clock labels."""
    if not interval or not all(isinstance(value, str) and ":" not in value for value in interval):
        return interval
    try:
        return [float(value) for value in interval]
    except ValueError:
        return interval


def _interval_score(
    answer: str,
    interval: list[Any],
    units: list[str],
    *,
    repair_numeric_strings: bool,
) -> Score:
    if repair_numeric_strings:
        interval = _coerce_numeric_string_interval(interval)

    normalized_answer = _normalize_unit_text(answer)
    unit_correct: bool | None = None if not units else False
    for unit in units:
        if _normalize_unit_text(unit) in normalized_answer:
            unit_correct = True

    if isinstance(interval[0], str):
        left = _time_to_seconds(interval[0].split(":"))
        right = _time_to_seconds(interval[1].split(":"))
        matches = TIME_RE.findall(answer)
        if not matches:
            return Score(False, unit_correct)
        predicted = float(_time_to_seconds(matches[0]))
    else:
        left, right = float(interval[0]), float(interval[1])
        numbers = extract_numbers(answer)
        if not numbers or math.isinf(numbers[-1]) or math.isnan(numbers[-1]):
            return Score(False, unit_correct)
        predicted = float(numbers[-1])

    if predicted < left or predicted > right:
        epsilon = 1e-6
        error = min(
            abs((predicted - left) / (left + epsilon)),
            abs((predicted - right) / (right + epsilon)),
        )
        return Score(False, unit_correct, error)
    return Score(True, unit_correct, 0.0)


def _is_better(candidate: Score, incumbent: Score | None) -> bool:
    if incumbent is None:
        return True
    candidate_unit = True if candidate.unit is None else candidate.unit
    incumbent_unit = True if incumbent.unit is None else incumbent.unit
    if int(candidate.value) + int(candidate_unit) > int(incumbent.value) + int(incumbent_unit):
        return True
    return (
        candidate.number_error_rate is not None
        and incumbent.number_error_rate is not None
        and candidate.number_error_rate < incumbent.number_error_rate
    )


def score_answer(
    answer: str | ParsedAnswer,
    evaluator: str,
    evaluator_kwargs: str | dict[str, Any],
    *,
    repair_numeric_strings: bool = False,
) -> Score:
    """Score one response with official semantics plus one opt-in annotation repair.

    The default is parity-oriented. ``repair_numeric_strings=True`` changes only
    intervals such as ["60", "60"] to [60.0, 60.0], while preserving HH:MM labels.
    """
    if isinstance(answer, ParsedAnswer):
        answer = "" if answer.value is None else f"{answer.value} {answer.unit}".strip()
    answer = normalize_string(extract_answer(answer))
    spec = json.loads(evaluator_kwargs) if isinstance(evaluator_kwargs, str) else evaluator_kwargs
    if evaluator == "interval_matching":
        return _interval_score(
            answer,
            spec["interval"],
            spec.get("units", []),
            repair_numeric_strings=repair_numeric_strings,
        )
    if evaluator == "multi_interval_matching":
        intervals = spec["intervals"]
        units = spec.get("units", []) or ([[]] * len(intervals))
        best: Score | None = None
        for interval, accepted_units in zip(intervals, units):
            candidate = _interval_score(
                answer,
                interval,
                accepted_units,
                repair_numeric_strings=repair_numeric_strings,
            )
            if candidate.full:
                return candidate
            if _is_better(candidate, best):
                best = candidate
        if best is None:
            raise ValueError("multi_interval_matching received no candidate intervals")
        return best
    raise ValueError(f"Unsupported evaluator: {evaluator}")
