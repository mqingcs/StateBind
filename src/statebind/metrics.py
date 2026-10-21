from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np
from scipy.stats import norm


def clustered_accuracy_interval(
    rows: list[dict[str, Any]],
    *,
    cluster_key: str = "round2_id",
    outcome_key: str = "correct",
    seed: int = 20260813,
    draws: int = 5000,
) -> dict[str, float | int | None]:
    if not rows:
        return {"accuracy": None, "ci_low": None, "ci_high": None, "n": 0, "clusters": 0}
    clusters: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        clusters[str(row[cluster_key])].append(float(bool(row[outcome_key])))
    keys = sorted(clusters)
    accuracy = float(np.mean([value for values in clusters.values() for value in values]))
    rng = np.random.default_rng(seed)
    samples = np.empty(draws, dtype=float)
    for index in range(draws):
        selected = rng.choice(keys, size=len(keys), replace=True)
        samples[index] = np.mean([value for key in selected for value in clusters[str(key)]])
    return {
        "accuracy": accuracy,
        "ci_low": float(np.quantile(samples, 0.025)),
        "ci_high": float(np.quantile(samples, 0.975)),
        "n": len(rows),
        "clusters": len(keys),
    }


def delta_75(distance_accuracy: dict[int, float]) -> float | None:
    points = sorted((int(distance), float(value)) for distance, value in distance_accuracy.items())
    if not points:
        return None
    distances = np.asarray([point[0] for point in points], dtype=float)
    accuracy = np.maximum.accumulate([point[1] for point in points])
    if accuracy[0] >= 0.75:
        return float(distances[0])
    for index in range(1, len(points)):
        if accuracy[index] < 0.75:
            continue
        x0, x1 = math.log2(distances[index - 1]), math.log2(distances[index])
        y0, y1 = float(accuracy[index - 1]), float(accuracy[index])
        if y1 == y0:
            return float(distances[index])
        fraction = (0.75 - y0) / (y1 - y0)
        return float(2 ** (x0 + fraction * (x1 - x0)))
    return None


def binary_signal_detection(
    *, hits: int, signal_n: int, false_alarms: int, noise_n: int
) -> dict[str, float | int | None]:
    if signal_n <= 0 or noise_n <= 0:
        return {
            "hits": hits,
            "signal_n": signal_n,
            "false_alarms": false_alarms,
            "noise_n": noise_n,
            "tpr": None,
            "fpr": None,
            "d_prime": None,
            "criterion": None,
        }
    tpr = hits / signal_n
    fpr = false_alarms / noise_n
    corrected_tpr = (hits + 0.5) / (signal_n + 1)
    corrected_fpr = (false_alarms + 0.5) / (noise_n + 1)
    z_hit = float(norm.ppf(corrected_tpr))
    z_false = float(norm.ppf(corrected_fpr))
    return {
        "hits": hits,
        "signal_n": signal_n,
        "false_alarms": false_alarms,
        "noise_n": noise_n,
        "tpr": tpr,
        "fpr": fpr,
        "d_prime": z_hit - z_false,
        "criterion": -0.5 * (z_hit + z_false),
    }
