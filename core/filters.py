"""MoCapGate — фильтры движения: One Euro (Casiez et al., 2012) и медиана.

One Euro гасит дрожание на медленных участках и почти не запаздывает на быстрых:
частота среза растёт со скоростью сигнала. Ровно то, что нужно для покадровой позы.
"""
from __future__ import annotations
import math


class OneEuro:
    def __init__(self, fps: float, min_cutoff: float = 1.0, beta: float = 0.3, d_cutoff: float = 1.0):
        self.dt = 1.0 / fps
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x = None
        self.dx = None

    def _alpha(self, cutoff: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / self.dt)

    def __call__(self, x: list[float]) -> list[float]:
        if self.x is None:
            self.x, self.dx = list(x), [0.0] * len(x)
            return list(x)
        a_d = self._alpha(self.d_cutoff)
        dx = [(xi - pi) / self.dt for xi, pi in zip(x, self.x)]
        self.dx = [a_d * d + (1 - a_d) * p for d, p in zip(dx, self.dx)]
        out = []
        for i, xi in enumerate(x):
            a = self._alpha(self.min_cutoff + self.beta * abs(self.dx[i]))
            out.append(a * xi + (1 - a) * self.x[i])
        self.x = out
        return out


def one_euro_series(series: list[list[float]], fps: float, strength: float) -> list[list[float]]:
    """Сгладить ряд векторов. strength 0 — без сглаживания, 1 — сильное."""
    if strength <= 0 or not series:
        return [list(v) for v in series]
    # strength → частота среза: 0.1 → ~4 Гц (легко), 1 → ~0.4 Гц (сильно)
    f = OneEuro(fps, min_cutoff=max(0.05, 4.0 * (1 - strength) + 0.4 * strength), beta=0.4)
    return [f(v) for v in series]


def median_filter(values: list[float], radius: int) -> list[float]:
    n = len(values)
    out = []
    for i in range(n):
        w = sorted(values[max(0, i - radius): min(n, i + radius + 1)])
        out.append(w[len(w) // 2])
    return out
