"""Map analyzer reports into the renderer's display bundle.

A "bundle" is the single data contract the renderer consumes: meta, a verdict,
KPI rows, optional bar charts, findings, and a footer. Keeping this mapping in
one place means the terminal and Markdown surfaces stay in lockstep and the
agent-synthesis findings slot in next to the deterministic ones.
"""

from __future__ import annotations

from typing import Any

from .savings import project_savings


def _grade_from_score(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 78:
        return "B"
    if score >= 62:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def _empty_bundle(mode_label: str, reason: str, hint: str) -> dict[str, Any]:
    return {
        "meta": {"mode_label": mode_label, "subtitle": reason},
        "verdict": {"grade": "·", "headline": reason},
        "kpis": [],
        "charts": [],
        "findings": [],
        "footer": hint,
        "empty": True,
    }


def token_bundle(report: dict[str, Any]) -> dict[str, Any]:
    totals = report["totals"]
    findings = report["findings"]
    if totals.get("sessions", 0) == 0:
        return _empty_bundle(
            "Token efficiency",
            "No Claude Code sessions found to analyze.",
            "Looked under ~/.claude/projects (or --projects-root). Run some Claude "
            "Code sessions first, or point --projects-root at the right location.",
        )
    cache = totals["overall_cache_hit_ratio"]
    reclaim = totals["reclaimable_cache_usd"]
    cost = totals["est_total_cost_usd"]

    # Efficiency score: cache health dominates, penalized by reclaimable share.
    reclaim_share = (reclaim / cost) if cost else 0.0
    score = 100 * (0.6 * cache + 0.4 * (1 - min(1.0, reclaim_share)))
    grade = _grade_from_score(score)

    n_sess = totals["sessions"]
    headline = (
        f"{_pct(cache)} cache hit-rate across {n_sess} "
        f"session{'s' if n_sess != 1 else ''}, ~{_money(reclaim)} reclaimable."
    )

    # chronological cost trend (oldest to newest) for an at-a-glance sparkline
    per = [m for m in report.get("per_session", []) if m.get("started")]
    per.sort(key=lambda m: m.get("started") or "")
    trend = None
    if len(per) >= 3:
        trend = {
            "label": "Cost per session (oldest to newest)",
            "values": [m["est_cost_usd"] for m in per[-40:]],
            "note": f"latest {_money(per[-1]['est_cost_usd'])}",
        }

    worst = report.get("worst_sessions", [])
    chart_rows = [
        {
            "label": w["session_id"][:24],
            "value": w["waste_score"],
            "note": f"{w['waste_score']:.0f} waste · {_money(w['est_cost_usd'])}",
            "role": "high" if w["waste_score"] >= 30 else "medium" if w["waste_score"] >= 15 else "low",
        }
        for w in worst[:8]
    ]

    kpis = [
        {"label": "Sessions analyzed", "value": str(totals["sessions"])},
        {"label": "Estimated total cost", "value": _money(cost)},
        {"label": "Cache hit-rate", "value": _pct(cache),
         "role": "good" if cache >= 0.55 else "high"},
        {"label": "Reclaimable (cache)", "value": _money(reclaim),
         "role": "good" if reclaim < 0.01 else "medium"},
        {"label": "Input / output tokens",
         "value": f"{_human(totals['input_tokens'])} / {_human(totals['output_tokens'])}"},
    ]

    return {
        "meta": {
            "mode_label": "Token efficiency",
            "subtitle": f"{totals['sessions']} sessions · {_human(totals['input_tokens']+totals['cache_read_tokens'])} tokens of context processed",
        },
        "verdict": {"grade": grade, "headline": headline},
        "projection": project_savings(report.get("per_session", []), totals),
        "kpis": kpis,
        "trend": trend,
        "charts": [{"title": "Highest-waste sessions", "rows": chart_rows}] if chart_rows else [],
        "findings": findings,
        "footer": "Deterministic pass. Run with an agent synthesis step for tailored CLAUDE.md / settings edits.",
    }


def repo_bundle(report: dict[str, Any]) -> dict[str, Any]:
    summary = report["summary"]
    findings = report["findings"]
    if summary.get("files", 0) == 0:
        return _empty_bundle(
            "Repo structure",
            "No files found to scan.",
            "Pass --repo PATH pointing at a git repo (or a directory with source files).",
        )
    score = report.get("health_score", 50.0)
    grade = _grade_from_score(score)

    kpis = [
        {"label": "Files scanned", "value": _human(summary["files"])},
        {"label": "Repo size (tracked)", "value": _bytes(summary["bytes"])},
        {"label": "Reclaimable size", "value": _bytes(summary["reclaimable_bytes"]),
         "role": "good" if summary["reclaimable_bytes"] < 50_000 else "medium"},
        {"label": "Dead / junk artifacts", "value": str(summary["junk_count"]),
         "role": "good" if summary["junk_count"] == 0 else "high"},
        {"label": "Largest file", "value": f"{summary.get('largest_file','-')} ({_bytes(summary.get('largest_bytes',0))})"},
    ]
    chart_rows = [
        {"label": c["label"], "value": c["bytes"], "note": _bytes(c["bytes"]),
         "role": "medium"}
        for c in report.get("size_by_area", [])[:8]
    ]
    headline = (
        f"{summary['junk_count']} junk artifacts, {_bytes(summary['reclaimable_bytes'])} "
        f"reclaimable across {_human(summary['files'])} files."
    )
    return {
        "meta": {
            "mode_label": "Repo structure",
            "subtitle": f"{report.get('repo','repo')} · {_human(summary['files'])} files · {_bytes(summary['bytes'])}",
        },
        "verdict": {"grade": grade, "headline": headline},
        "kpis": kpis,
        "charts": [{"title": "Size by area", "rows": chart_rows}] if chart_rows else [],
        "findings": findings,
        "footer": "Static pass. Pair with session evidence (--mode both) to rank by agent friction.",
    }


def combined_bundle(token_rep: dict[str, Any], repo_rep: dict[str, Any]) -> dict[str, Any]:
    tb = token_bundle(token_rep)
    rb = repo_bundle(repo_rep)
    findings = tb["findings"] + rb["findings"]
    findings.sort(key=lambda f: (-_SEV.get(f.get("severity", "info"), 0), -(f.get("impact_usd") or 0)))
    return {
        "meta": {
            "mode_label": "Token + repo (combined)",
            "subtitle": tb["meta"]["subtitle"] + "  ·  " + rb["meta"]["subtitle"],
        },
        "verdict": {
            # surface the WORSE of the two grades (F worst); higher letter = worse
            "grade": max(tb["verdict"]["grade"], rb["verdict"]["grade"]),
            "headline": tb["verdict"]["headline"] + "  " + rb["verdict"]["headline"],
        },
        "projection": tb.get("projection"),
        "kpis": tb["kpis"][:3] + rb["kpis"][:3],
        "charts": tb["charts"] + rb["charts"],
        "findings": findings,
        "footer": "Combined pass. Highest-leverage items first across both intents.",
    }


_SEV = {"high": 3, "medium": 2, "low": 1, "info": 0}


def _pct(x: float) -> str:
    return f"{x*100:.0f}%"


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _human(n: int) -> str:
    for unit in ("", "K", "M", "B"):
        if abs(n) < 1000:
            return f"{n:.0f}{unit}" if unit else f"{n}"
        n /= 1000.0
    return f"{n:.1f}T"


def _bytes(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(f) < 1024:
            return f"{f:.0f}{unit}" if unit == "B" else f"{f:.1f}{unit}"
        f /= 1024.0
    return f"{f:.1f}TB"
