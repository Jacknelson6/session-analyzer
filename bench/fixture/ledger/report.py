"""Summaries computed over a LedgerStore."""

from collections import defaultdict

from .store import LedgerStore


def totals_by_category(store: LedgerStore) -> dict[str, float]:
    """Sum transaction amounts grouped by category."""
    out: dict[str, float] = defaultdict(float)
    for t in store.all():
        out[t.category] += t.amount
    return dict(out)


def grand_total(store: LedgerStore) -> float:
    """Sum of all transaction amounts."""
    return sum(t.amount for t in store.all())
