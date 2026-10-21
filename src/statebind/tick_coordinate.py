from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ProjectiveTickCoordinate:
    """One-dimensional projective map from tick index to axis position.

    The map has the form ``u(k) = (a*k + b) / (c*k + 1)``.  Three
    non-collinear tick observations determine the three coefficients.  The
    affine model is the special case ``c == 0``.
    """

    a: float
    b: float
    c: float

    @classmethod
    def from_three_ticks(
        cls,
        tick_indices: np.ndarray | list[float],
        axis_positions: np.ndarray | list[float],
    ) -> ProjectiveTickCoordinate:
        indices = np.asarray(tick_indices, dtype=float)
        positions = np.asarray(axis_positions, dtype=float)
        if indices.shape != (3,) or positions.shape != (3,):
            raise ValueError("exactly three tick indices and positions are required")
        if len(np.unique(indices)) != 3:
            raise ValueError("tick indices must be distinct")
        matrix = np.column_stack(
            [indices, np.ones(3, dtype=float), -indices * positions]
        )
        try:
            a, b, c = np.linalg.solve(matrix, positions)
        except np.linalg.LinAlgError as exc:
            raise ValueError("the three tick observations are degenerate") from exc
        model = cls(float(a), float(b), float(c))
        reconstructed = model.position(indices)
        if not np.allclose(reconstructed, positions, atol=1e-6, rtol=1e-8):
            raise ValueError("the three tick observations do not define a stable map")
        return model

    @classmethod
    def from_two_adjacent_ticks(
        cls, lower_axis_position: float, higher_axis_position: float
    ) -> ProjectiveTickCoordinate:
        lower = float(lower_axis_position)
        higher = float(higher_axis_position)
        if higher <= lower:
            raise ValueError("higher_axis_position must exceed lower_axis_position")
        return cls(higher - lower, lower, 0.0)

    def position(self, tick_index: float | np.ndarray) -> float | np.ndarray:
        index = np.asarray(tick_index, dtype=float)
        denominator = self.c * index + 1.0
        if np.any(np.isclose(denominator, 0.0, atol=1e-9)):
            raise ValueError("tick index reaches the projective singularity")
        result = (self.a * index + self.b) / denominator
        return float(result) if result.ndim == 0 else result

    def index(self, axis_position: float | np.ndarray) -> float | np.ndarray:
        position = np.asarray(axis_position, dtype=float)
        denominator = position * self.c - self.a
        if np.any(np.isclose(denominator, 0.0, atol=1e-9)):
            raise ValueError("axis position reaches the projective vanishing point")
        result = (self.b - position) / denominator
        return float(result) if result.ndim == 0 else result

    def offset_position(self, axis_position: float, distance_ticks: float) -> float:
        origin_index = self.index(float(axis_position))
        return float(self.position(origin_index + float(distance_ticks)))

    def is_monotone_over(self, tick_indices: np.ndarray | list[float]) -> bool:
        positions = np.asarray(self.position(np.asarray(tick_indices, dtype=float)))
        return bool(np.all(np.diff(positions) > 0))
