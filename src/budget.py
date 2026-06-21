"""Token budget ledger.

The skill promises a hard ceiling (200K single-intent, 400K combined). The heavy
extraction is deterministic and free; the budget governs how much *agent-read*
material the run emits, the digest size, shard count, and per-shard truncation,
so the synthesis stage cannot blow the cap. This ledger is the single place that
decides how big the emitted artifacts may be.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CHARS_PER_TOKEN = 4


@dataclass
class Budget:
    cap_tokens: int
    spent_tokens: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return max(0, self.cap_tokens - self.spent_tokens)

    def can_afford(self, tokens: int) -> bool:
        return self.spent_tokens + tokens <= self.cap_tokens

    def charge(self, tokens: int, label: str = "") -> bool:
        if not self.can_afford(tokens):
            self.notes.append(f"SKIPPED {label}: would exceed cap ({tokens} > {self.remaining} left)")
            return False
        self.spent_tokens += tokens
        if label:
            self.notes.append(f"+{tokens} {label} (spent {self.spent_tokens}/{self.cap_tokens})")
        return True

    def charge_chars(self, chars: int, label: str = "") -> bool:
        return self.charge(round(chars / CHARS_PER_TOKEN), label)

    def shard_allowance(self, reserve_frac: float = 0.35) -> int:
        """Tokens available for agent-read shards after reserving synthesis headroom."""
        return int(self.remaining * (1 - reserve_frac))

    def to_dict(self) -> dict:
        return {
            "cap_tokens": self.cap_tokens,
            "spent_tokens": self.spent_tokens,
            "remaining": self.remaining,
            "notes": self.notes,
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))


def cap_for_mode(mode: str, override: int | None = None) -> int:
    if override:
        return override
    return 400_000 if mode == "both" else 200_000
