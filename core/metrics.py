"""Lightweight latency tracking for the voice assistant loop."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class LatencyTracker:
    """Collect phase timings for one assistant request."""

    started_at: float = field(default_factory=time.perf_counter)
    last_mark: float = field(default_factory=time.perf_counter)
    phases: dict[str, float] = field(default_factory=dict)

    def mark(self, phase: str) -> None:
        now = time.perf_counter()
        self.phases[phase] = now - self.last_mark
        self.last_mark = now

    @property
    def total(self) -> float:
        return time.perf_counter() - self.started_at

    def as_dict(self) -> dict[str, float]:
        data = {name: round(value, 3) for name, value in self.phases.items()}
        data["total"] = round(sum(self.phases.values()), 3)
        return data

    def summary(self) -> str:
        parts = [f"{name}={value:.2f}s" for name, value in self.phases.items()]
        parts.append(f"total={sum(self.phases.values()):.2f}s")
        return " | ".join(parts)

