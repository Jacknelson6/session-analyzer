"""Project token savings from this tool's proven levers onto the user's real usage.

Answers "what would I save?" with a number grounded in two things: the user's
own measured token usage, and this repo's benchmark. Honest by construction --
the orientation-map rate (the benchmark's 41-47%) is applied ONLY to the sessions
that actually show re-exploration, which is the regime the benchmark measured the
win in (OPTIMIZATION_LOG round 37: the win is in re-read / exploration-heavy work,
not cheap navigation; there a generic doc is flat-to-negative). Sessions with no
re-exploration project ~0 from the map, deliberately.

Everything here is a clearly-labeled estimate. The cache-recovery figure is the
already-measured reclaimable amount; the map figure is a prediction.
"""

from __future__ import annotations

from typing import Any

# The benchmark's measured orientation-map savings band (Sonnet 4.6 .. Opus 4.8),
# task success held. See README "Proven on SA-Bench" and bench/.
MAP_RATE_LOW = 0.41
MAP_RATE_HIGH = 0.47


def _ctx(m: dict[str, Any]) -> int:
    return m.get("input_tokens", 0) + m.get("cache_read_tokens", 0) + m.get("cache_creation_tokens", 0)


def project_savings(per_session: list[dict[str, Any]], totals: dict[str, Any]) -> dict[str, Any]:
    """Project savings from adopting the orientation map, plus recoverable cache.

    Returns a small dict the renderer and digest surface. The map projection is
    scoped to sessions that re-read files (the signal the map removes), so it
    matches the benchmark's regime instead of being sprayed across all tokens.
    """
    total_ctx = _ctx(totals)

    # Eligible = sessions where Claude re-read the same file(s): the clearest
    # "re-explored the tree" signal, and exactly what the orientation map removes.
    eligible = [m for m in per_session if m.get("reread_files")]
    eligible_ctx = sum(_ctx(m) for m in eligible)
    eligible_cost = sum(m.get("est_cost_usd", 0.0) for m in eligible)

    map_tokens_low = round(eligible_ctx * MAP_RATE_LOW)
    map_tokens_high = round(eligible_ctx * MAP_RATE_HIGH)
    map_usd_low = round(eligible_cost * MAP_RATE_LOW, 2)
    map_usd_high = round(eligible_cost * MAP_RATE_HIGH, 2)

    pct_low = (map_tokens_low / total_ctx) if total_ctx else 0.0
    pct_high = (map_tokens_high / total_ctx) if total_ctx else 0.0

    return {
        "total_sessions": len(per_session),
        "map_eligible_sessions": len(eligible),
        "total_context_tokens": total_ctx,
        "eligible_context_tokens": eligible_ctx,
        "rate_low": MAP_RATE_LOW,
        "rate_high": MAP_RATE_HIGH,
        "map_tokens_low": map_tokens_low,
        "map_tokens_high": map_tokens_high,
        "map_usd_low": map_usd_low,
        "map_usd_high": map_usd_high,
        "pct_low": round(pct_low, 4),
        "pct_high": round(pct_high, 4),
        "cache_reclaimable_usd": round(totals.get("reclaimable_cache_usd", 0.0), 2),
    }


def _human_tokens(n: int) -> str:
    f = float(n)
    for unit in ("", "K", "M", "B"):
        if abs(f) < 1000:
            return f"{f:.0f}{unit}" if unit else f"{int(f)}"
        f /= 1000.0
    return f"{f:.1f}T"


def projection_lines(p: dict[str, Any]) -> list[str]:
    """Render the projection as plain text lines (shared by terminal/markdown/digest)."""
    if not p:
        return []
    lines: list[str] = []
    elig = p["map_eligible_sessions"]
    if elig and p["map_tokens_high"] > 0:
        tok = f"~{_human_tokens(p['map_tokens_low'])}-{_human_tokens(p['map_tokens_high'])} tokens"
        usd = f"~${p['map_usd_low']:,.2f}-${p['map_usd_high']:,.2f}"
        pct = f"~{p['pct_low']*100:.0f}-{p['pct_high']*100:.0f}% of all tokens"
        lines.append(f"Adopt the orientation map: {tok} ({usd}), {pct}.")
        lines.append(
            f"basis: {elig} of {p['total_sessions']} sessions re-explored the tree; "
            f"benchmark rate {p['rate_low']*100:.0f}-{p['rate_high']*100:.0f}% applied to the "
            f"{_human_tokens(p['eligible_context_tokens'])} tokens those sessions processed."
        )
    else:
        lines.append(
            "Orientation map: little to gain here -- no repeated re-exploration "
            "detected (the map's win is in re-read / exploration-heavy work)."
        )
    if p.get("cache_reclaimable_usd", 0) > 0:
        lines.append(f"Fix cache misses: ~${p['cache_reclaimable_usd']:,.2f} more recoverable (see findings).")
    return lines
