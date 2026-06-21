"""Token-to-dollar conversion.

Prices are per million tokens (USD). They are deliberately editable and
versioned here rather than hard-coded at call sites: model prices change, and a
single source keeps every cost projection consistent. Cache-read is charged at a
fraction of the input rate, which is exactly why low cache-hit ratios are
expensive, the analyzer's central token-efficiency lever.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float
    cache_write_per_mtok: float


# Conservative defaults aligned to a frontier-tier model. Override via
# `analyze --price-input ... --price-output ...` for an exact account.
DEFAULT_PRICE = Price(
    input_per_mtok=3.00,
    output_per_mtok=15.00,
    cache_read_per_mtok=0.30,
    cache_write_per_mtok=3.75,
)


def cost_usd(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
    price: Price = DEFAULT_PRICE,
) -> float:
    return (
        input_tokens / 1e6 * price.input_per_mtok
        + output_tokens / 1e6 * price.output_per_mtok
        + cache_read_tokens / 1e6 * price.cache_read_per_mtok
        + cache_creation_tokens / 1e6 * price.cache_write_per_mtok
    )


def cache_miss_cost_usd(billable_input_tokens: int, price: Price = DEFAULT_PRICE) -> float:
    """Dollars that *would have* been cache-read rate had the prefix been cached.

    Used to size the prize from improving cache hit rate.
    """
    return billable_input_tokens / 1e6 * (price.input_per_mtok - price.cache_read_per_mtok)
