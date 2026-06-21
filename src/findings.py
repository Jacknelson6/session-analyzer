"""The shared Finding type used by every analyzer intent.

A Finding is the atomic unit of the report: one specific, evidence-backed
problem with a severity, an estimated dollar/efficiency impact, and a concrete
recommendation. Both the deterministic extractors and the agent's synthesis emit
Findings, so the renderer can present them uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SEVERITIES = ("high", "medium", "low", "info")


@dataclass
class Finding:
    id: str
    title: str
    severity: str  # one of SEVERITIES
    category: str  # "tokens" | "repo" | "structure" | ...
    evidence: str
    recommendation: str
    impact_usd: float = 0.0
    # Optional richer fields used by the repo intent / agent synthesis.
    locations: list[str] = field(default_factory=list)
    effort: str = "unknown"  # "trivial" | "small" | "medium" | "large"
    autofixable: bool = False
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            self.severity = "info"

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)
